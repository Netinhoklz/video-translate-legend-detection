import os
import time
import json
import csv
import uuid
import boto3
import cv2
import requests
import numpy as np
from chalice import Chalice, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from werkzeug.utils import secure_filename
import logging
import zipfile
from dotenv import load_dotenv
from moviepy import VideoFileClip, AudioFileClip
import subprocess

# Load environment variables from .env file
load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Chalice(app_name='video-processor')

# Configuration
S3_BUCKET = os.environ.get("S3_BUCKET", "your-bucket-name")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# AWS Clients
s3_client = boto3.client('s3', region_name=AWS_REGION)
transcribe_client = boto3.client('transcribe', region_name=AWS_REGION)
translate_client = boto3.client('translate', region_name=AWS_REGION)
rekognition_client = boto3.client('rekognition', region_name=AWS_REGION)

# Use /tmp for uploads if running in Lambda (read-only file system elsewhere)
if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    UPLOAD_FOLDER = '/tmp'
else:
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Template Engine Setup
template_loader = FileSystemLoader(searchpath="./templates")
template_env = Environment(
    loader=template_loader,
    autoescape=select_autoescape(['html', 'xml'])
)

def render_template(template_name, **kwargs):
    try:
        template = template_env.get_template(template_name)
        return template.render(**kwargs)
    except Exception as e:
        logger.error(f"Error rendering template {template_name}: {e}")
        return str(e)

@app.route('/')
def index():
    return Response(body=render_template('index.html'),
                    status_code=200,
                    headers={'Content-Type': 'text/html'})

@app.route('/uploads/{filename}')
def uploaded_file(filename):
    # In a real serverless app, you should serve these from S3.
    # This is a fallback for the current logic.
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Determine content type (basic)
        content_type = 'application/octet-stream'
        if filename.endswith('.mp4'):
            content_type = 'video/mp4'
        elif filename.endswith('.zip'):
            content_type = 'application/zip'
        elif filename.endswith('.csv'):
            content_type = 'text/csv'
            
        return Response(body=content,
                        status_code=200,
                        headers={'Content-Type': content_type})
    else:
        return Response(body='File not found', status_code=404)

@app.route('/get-presigned-url', methods=['POST'])
def get_presigned_url():
    try:
        request = app.current_request
        data = request.json_body
        filename = data.get('filename')
        file_type = data.get('file_type')
        
        if not filename:
            return Response(body={'error': 'Filename is required'}, status_code=400)

        job_id = str(uuid.uuid4())
        s3_key = f"uploads/{job_id}_{secure_filename(filename)}"
        
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': S3_BUCKET,
                'Key': s3_key,
                'ContentType': file_type
            },
            ExpiresIn=3600
        )
        
        return {
            'url': presigned_url,
            'key': s3_key,
            'job_id': job_id,
            'filename': secure_filename(filename)
        }
    except Exception as e:
        logger.error(f"Error generating presigned URL: {e}")
        return Response(body={'error': str(e)}, status_code=500)

@app.route('/process-video', methods=['POST'])
def process_video():
    try:
        request = app.current_request
        data = request.json_body
        s3_key = data.get('key')
        job_id = data.get('job_id')
        filename = data.get('filename')
        
        if not s3_key or not job_id or not filename:
            return Response(body={'error': 'Missing required parameters'}, status_code=400)

        logger.info(f"Processing video from S3: {s3_key}")
        
        # Download video from S3 to local temp for processing
        input_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{filename}")
        logger.info(f"Downloading to: {input_path}")
        s3_client.download_file(S3_BUCKET, s3_key, input_path)

        # 2. Start Transcribe Job
        transcribe_job_name = f"transcribe_{job_id}"
        media_format = filename.split('.')[-1]
        logger.info(f"Starting Transcribe job: {transcribe_job_name} (Format: {media_format})")
        
        try:
            transcribe_client.start_transcription_job(
                TranscriptionJobName=transcribe_job_name,
                Media={'MediaFileUri': f"s3://{S3_BUCKET}/{s3_key}"},
                MediaFormat=media_format,
                LanguageCode='pt-BR'
            )
        except transcribe_client.exceptions.ConflictException:
            logger.info("Transcription job already exists, reusing...")

        # 3. Start Rekognition Job (Label Detection)
        logger.info("Starting Rekognition job...")
        rekognition_response = rekognition_client.start_label_detection(
            Video={'S3Object': {'Bucket': S3_BUCKET, 'Name': s3_key}},
            MinConfidence=70
        )
        rekognition_job_id = rekognition_response['JobId']

        # 4. Poll for Completion (Synchronous for simplicity, but ideally async)
        # Wait for Transcribe
        logger.info("Waiting for Transcribe job...")
        while True:
            status = transcribe_client.get_transcription_job(TranscriptionJobName=transcribe_job_name)
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            if job_status in ['COMPLETED', 'FAILED']:
                break
            logger.info(f"Transcribe status: {job_status}")
            time.sleep(2)
        
        if job_status == 'FAILED':
            failure_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown Reason')
            logger.error(f"Transcription failed: {failure_reason}")
            raise Exception(f"Transcription failed: {failure_reason}")

        logger.info("Transcription completed.")
        transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
        transcript_response = requests.get(transcript_uri)
        transcript_data = transcript_response.json()
        
        # Handle case where no transcript is found
        if not transcript_data['results']['transcripts']:
             transcript_text = ""
             logger.warning("No transcript text found.")
        else:
             transcript_text = transcript_data['results']['transcripts'][0]['transcript']

        # 5. Translate Text
        logger.info("Translating text...")
        if transcript_text:
            translate_response = translate_client.translate_text(
                Text=transcript_text,
                SourceLanguageCode='pt',
                TargetLanguageCode='en'
            )
            translated_text = translate_response['TranslatedText']
        else:
            translated_text = ""

        # Wait for Rekognition
        logger.info("Waiting for Rekognition job...")
        while True:
            rek_status = rekognition_client.get_label_detection(JobId=rekognition_job_id)
            if rek_status['JobStatus'] in ['SUCCEEDED', 'FAILED']:
                break
            time.sleep(2)

        if rek_status['JobStatus'] == 'FAILED':
            raise Exception("Rekognition failed")

        all_labels = rek_status['Labels'] # List of labels with timestamps
        
        # Filter labels: Only keep those mentioned in the translated text
        # We use the English translation because Rekognition labels are in English
        labels = []
        if translated_text:
            normalized_text = translated_text.lower()
            for label_item in all_labels:
                name = label_item['Label']['Name'].lower()
                # Check if label name is in text (simple substring match)
                if name in normalized_text:
                    labels.append(label_item)
        else:
            # If no text, maybe show nothing or everything? 
            # Requirement says "mentioned in audio", so if no audio, no objects.
            labels = []

        logger.info(f"Filtered labels: {[l['Label']['Name'] for l in labels]}")

        # 6. Process Video (Overlay)
        temp_video_path = os.path.join(UPLOAD_FOLDER, f"temp_{job_id}_{filename}")
        output_path = os.path.join(UPLOAD_FOLDER, f"processed_{job_id}_{filename}")
        
        # Process video frames (silent)
        process_video_overlay(input_path, temp_video_path, translated_text, labels)
        
        # Add Audio back to the video using ffmpeg directly
        try:
            logger.info("Merging audio with ffmpeg...")
            
            # ffmpeg command: Re-encode to ensure compatibility
            # We re-encode video to H.264 (libx264) and audio to AAC to ensure standard format
            subprocess.run([
                'ffmpeg', '-y',
                '-i', temp_video_path,
                '-i', input_path,
                '-c:v', 'libx264',  # Re-encode video to H.264
                '-c:a', 'aac',      # Re-encode audio to AAC
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-pix_fmt', 'yuv420p', # Ensure compatible pixel format for players
                '-shortest',
                output_path
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            logger.info("Audio merge successful.")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error merging audio with ffmpeg: {e.stderr.decode()}")
            # Fallback handled below
        except Exception as e:
            logger.error(f"Unexpected error merging audio: {e}")

        # Give OS time to release file locks (crucial for Windows)
        time.sleep(1)

        # Check if output was created successfully
        if os.path.exists(output_path):
            # Success, remove temp file
            if os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                except Exception as e:
                    logger.warning(f"Could not remove temp file (non-critical): {e}")
        else:
            # Fallback: If audio merge failed, use the silent video as the result
            logger.warning("Audio merge failed, falling back to silent video.")
            if os.path.exists(temp_video_path):
                try:
                    # Try to rename, if that fails, try to copy then remove
                    os.rename(temp_video_path, output_path)
                except Exception as e:
                    logger.error(f"Could not rename temp file to output: {e}")
                    raise e

        # 7. Create ZIP bundle with Video and Transcript
        csv_filename = f"transcript_{job_id}.csv"
        csv_path = os.path.join(UPLOAD_FOLDER, csv_filename)
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Portuguese", "English"])
            writer.writerow([transcript_text, translated_text])
        
        zip_filename = f"result_{job_id}.zip"
        zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.write(output_path, os.path.basename(output_path))
            zipf.write(csv_path, csv_filename)

        # Upload processed video to S3
        processed_s3_key = f"processed/{job_id}_{filename}"
        logger.info(f"Uploading processed video to S3: {processed_s3_key}")
        s3_client.upload_file(
            output_path, 
            S3_BUCKET, 
            processed_s3_key, 
            ExtraArgs={
                'ContentType': 'video/mp4',
                'ContentDisposition': 'inline'
            }
        )

        # Upload ZIP to S3
        zip_s3_key = f"processed/{zip_filename}"
        logger.info(f"Uploading ZIP to S3: {zip_s3_key}")
        s3_client.upload_file(zip_path, S3_BUCKET, zip_s3_key, ExtraArgs={'ContentType': 'application/zip'})

        # Generate Presigned URLs for Download
        local_video_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': processed_s3_key},
            ExpiresIn=3600
        )
        
        local_zip_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': zip_s3_key},
            ExpiresIn=3600
        )

        # Cleanup local files (optional but good for Lambda)
        try:
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_path): os.remove(output_path)
            if os.path.exists(zip_path): os.remove(zip_path)
            if os.path.exists(csv_path): os.remove(csv_path)
        except Exception as e:
            logger.warning(f"Error cleaning up files: {e}")

        # Prepare unique objects list for display
        unique_objects = {}
        for label in labels:
            name = label['Label']['Name']
            conf = label['Label']['Confidence']
            if name not in unique_objects or conf > unique_objects[name]:
                unique_objects[name] = conf

        display_objects = [{'Name': k, 'Confidence': v} for k, v in unique_objects.items()]

        # Return JSON with redirect URL or HTML content
        # Since we are using AJAX, we should probably return JSON and let frontend redirect
        # But to keep it simple and reuse the template, we can render it and return the HTML
        return Response(body=render_template('result.html', 
                               video_url=local_video_url, 
                               download_url=local_zip_url,
                               transcript_pt=transcript_text, 
                               transcript_en=translated_text,
                               objects=display_objects,
                               version="v3.0"),
                        status_code=200,
                        headers={
                            'Content-Type': 'text/html',
                            'Cache-Control': 'no-cache, no-store, must-revalidate',
                            'Pragma': 'no-cache',
                            'Expires': '0'
                        })

    except Exception as e:
        logger.error(f"Error processing video: {str(e)}", exc_info=True)
        return Response(body={'error': str(e)}, status_code=500)

def process_video_overlay(input_path, output_path, subtitle_text, labels):
    cap = cv2.VideoCapture(input_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # Organize labels by timestamp (ms)
    labels_by_time = {}
    for label in labels:
        timestamp = label['Timestamp']
        if timestamp not in labels_by_time:
            labels_by_time[timestamp] = []
        labels_by_time[timestamp].append(label['Label'])

    # Simple subtitle splitting (very basic)
    words = subtitle_text.split()
    chunk_size = 5 # words per chunk
    chunks = [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    chunk_duration = duration / len(chunks) if chunks else 0

    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        current_time_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        
        # Draw Subtitles
        if chunks:
            chunk_index = int(current_time_ms / 1000 / chunk_duration)
            if chunk_index < len(chunks):
                text = chunks[chunk_index]
                
                # Calculate text size for centering
                font = cv2.FONT_HERSHEY_TRIPLEX
                font_scale = 1
                thickness = 2
                (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
                
                x = (width - text_width) // 2
                y = height - 50
                
                # Draw background box
                padding = 10
                cv2.rectangle(frame, (x - padding, y - text_height - padding), (x + text_width + padding, y + padding), (0, 0, 0), -1)
                
                # Draw text
                cv2.putText(frame, text, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        # Draw Bounding Boxes (Approximate matching based on timestamp)
        # Rekognition gives timestamps. We need to find the closest one.
        # This is a simplification. Ideally we interpolate.
        closest_time = min(labels_by_time.keys(), key=lambda x: abs(x - current_time_ms)) if labels_by_time else None
        
        if closest_time and abs(closest_time - current_time_ms) < 500: # within 500ms
            for label in labels_by_time[closest_time]:
                for instance in label.get('Instances', []):
                    box = instance['BoundingBox']
                    left = int(box['Left'] * width)
                    top = int(box['Top'] * height)
                    w = int(box['Width'] * width)
                    h = int(box['Height'] * height)
                    
                    cv2.rectangle(frame, (left, top), (left + w, top + h), (0, 255, 0), 2)
                    cv2.putText(frame, label['Name'], (left, top - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        out.write(frame)
        frame_count += 1

    cap.release()
    out.release()

if __name__ == '__main__':
    print("Starting Chalice Local Server...")
    os.system("chalice local")
