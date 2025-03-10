from flask import Flask, request, jsonify
import google.generativeai as genai
import json
import requests
from PIL import Image
import io
from datetime import datetime, timedelta
import base64
import random
import time
import logging
from flask_cors import CORS
from threading import Thread
import uuid

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

API_URL_FLUX = ""
API_URL_Midjourney = ""
HF_HEADERS = {""}
genai.configure(api_key='')

# Storage for tasks and results
task_status = {}
task_results = {}

class Session:
    def __init__(self, original_data):
        self.original_data = original_data
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.task_ids = []

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.session_timeout = timedelta(hours=1)
        
    def create_session(self, task_id, data):
        session = Session(data)
        session.task_ids.append(task_id)
        self.sessions[task_id] = session
        return session
        
    def get_session(self, task_id):
        self._clean_expired_sessions()
        session = self.sessions.get(task_id)
        if session:
            session.last_used = datetime.now()
        return session
            
    def _clean_expired_sessions(self):
        current_time = datetime.now()
        expired_ids = [
            task_id for task_id, session in self.sessions.items()
            if current_time - session.created_at > self.session_timeout
        ]
        for task_id in expired_ids:
            del self.sessions[task_id]

# Initialize session manager
session_manager = SessionManager()

def query_huggingface(payload, API_URL, max_retries=3, initial_delay=1):
    """Query HuggingFace API with retries and exponential backoff"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting API call to {API_URL}, attempt {attempt + 1}/{max_retries}")
            response = requests.post(API_URL, headers=HF_HEADERS, json=payload)
            
            if response.status_code == 503:
                logger.warning("Service temporarily unavailable")
                raise requests.exceptions.RequestException("Service temporarily unavailable")
            
            if response.status_code == 200:
                logger.info("API call successful")
                return response
                
            response.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to generate image after {max_retries} attempts: {str(e)}")
                return None
                
            delay = initial_delay * (2 ** attempt)
            logger.info(f"Attempt {attempt + 1} failed, retrying in {delay} seconds...")
            time.sleep(delay)
    
    return None

def generate_marketing_content(input_data, product, platforms):
    """Generate marketing content for one or multiple platforms using Gemini model"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        platform_constraints = {
            "Twitter": "Ensure the full content is below 270 characters.",
            "LinkedIn": "Content should be professional and detailed (up to 125 words).",
            "Instagram": "Make the content engaging.",
            "Facebook": "Create balanced content suitable for a broad audience.",
        }
        
        if isinstance(platforms, str):
            platforms = [platforms]  # Convert single platform to list
        
        constraint = "Ensure content is engaging and effective."
        if "Twitter" in platforms:
            constraint = "Ensure the full content is below 270 characters to be compatible with Twitter while remaining engaging for other platforms."
        elif len(platforms) == 1:
            platform = platforms[0]
            constraint = platform_constraints.get(platform, constraint)
        
        input_prompt = f"""
            You are an expert in generating marketing content. Create unique marketing content based on the details below:
            - **Prompt**: {input_data['prompt']}
            - **Target Platform(s)**: {', '.join(platforms)}
            - **Product/Service**: {product}

            **Platform-Specific Constraint**: {constraint}

            Content Requirements:
            - Title: Short and engaging
            - Punchline: Attention-grabbing one-liner
            - Platform-optimized content: Must be 270 characters or less if Twitter is a target platform
            - 5 relevant hashtags
            - 5 important keywords

            Instructions:
            - Use plain text only (no special characters like *, _, or markdown symbols).
            - Return the response in JSON format with the keys: "Title", "Punchline", "Content", "Hashtags", "Keywords".
        """
        
        completion = model.generate_content([input_prompt])
        response_text = completion.text.strip()
        
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').strip()
            if response_text.endswith('```'):
                response_text = response_text[:-3].strip()
        
        return json.loads(response_text)
    
    except Exception as e:
        logging.error(f"Error generating marketing content: {str(e)}")
        raise






def generate_image(content, img_prompt,logo_data, backup_model=True):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        refinement_prompt = f"""
        Create only one detailed and creative prompt for generating a marketing image using the following details:
        
        Punchline: {content.get('Punchline', '')}
        Title: {content.get('Title', '')} and this is 
        img_prompt:{img_prompt}
        Please create an image that works well with this content.
        The image should be visually appealing, human-centric or Futuristic and Technological Themes and suitable for social media marketing.
        """
        
        note_in_prompt = """***Please create a versatile image that works well with the content. 
        Avoid unnecessary text, and ensure all text is grammatically correct and free of spelling errors for a professional and polished look.
        Include designated space for the punchline text to be overlay on the image.
        Ensure the upper 15% of the image, especially the upper right side, remains completely blank for logo placement***"""
        refined_completion = model.generate_content([refinement_prompt])
        refined_prompt = refined_completion.text.strip()
        refined_prompt = note_in_prompt + refined_prompt
        
        # Try primary model (FLUX)
        response = query_huggingface({"inputs": refined_prompt}, API_URL_FLUX)
        
        # If primary model fails and backup is enabled, try Midjourney
        if response is None and backup_model:
            response = query_huggingface({"inputs": refined_prompt}, API_URL_Midjourney)
        
        if response is not None:
            # Process and add logo to image
            image = Image.open(io.BytesIO(response.content))
            logo = Image.open(io.BytesIO(base64.b64decode(logo_data))).convert("RGBA")
            
            logo_size = (200, 100)
            logo = logo.resize(logo_size)
            image_width, image_height = image.size
            logo_position = (image_width - logo_size[0] - 10, 10)
            
            image_with_alpha = image.convert("RGBA")
            image_with_alpha.paste(logo, logo_position, logo)
            final_image = image_with_alpha.convert("RGB")
            
            buffered = io.BytesIO()
            final_image.save(buffered, format="JPEG", quality=90)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return img_str
            
        return None
            
    except Exception as e:
        logger.error(f"Error in image generation: {str(e)}")
        return None

def process_content_only(task_id, data):
    """Process only content generation asynchronously"""
    try:
        # Generate content
        content = generate_marketing_content(data, data['product'], data['platform'])
        task_status[task_id]['content_status'] = 'completed'
        task_results[task_id]['content'] = content
        task_status[task_id]['overall_status'] = 'completed'
        
    except Exception as e:
        task_status[task_id]['overall_status'] = 'failed'
        task_status[task_id]['error'] = str(e)
        logger.error(f"Error processing content for task {task_id}: {str(e)}")

def process_image_only(task_id, data, content):
    """Process only image generation asynchronously"""
    try:
        # Generate image
        image_base64 = generate_image(content,data['img_prompt'], data['logo'])
        img_str = 'data:image/jpeg;base64,' + image_base64 if image_base64 else None
        task_results[task_id]['image'] = img_str
        task_status[task_id]['image_status'] = 'completed'
        task_status[task_id]['overall_status'] = 'completed'
        
    except Exception as e:
        task_status[task_id]['overall_status'] = 'failed'
        task_status[task_id]['error'] = str(e)
        logger.error(f"Error processing image for task {task_id}: {str(e)}")

def process_request_async(task_id, data):
    """Process both content and image generation asynchronously"""
    try:
        # Generate content
        content = generate_marketing_content(data, data['product'], data['platform'])
        task_status[task_id]['content_status'] = 'completed'
        task_results[task_id]['content'] = content
        
        # Generate image
        image_base64 = generate_image(content,data['img_prompt'], data['logo'])
        img_str = 'data:image/jpeg;base64,' + image_base64 if image_base64 else None
        task_results[task_id]['image'] = img_str
        task_status[task_id]['image_status'] = 'completed'
        task_status[task_id]['overall_status'] = 'completed'
        
    except Exception as e:
        task_status[task_id]['overall_status'] = 'failed'
        task_status[task_id]['error'] = str(e)
        logger.error(f"Error processing task {task_id}: {str(e)}")

@app.route('/generate-marketing-content', methods=['POST'])
def generate_content():
    try:
        data = request.json
        required_fields = [
            'img_prompt', 'prompt', 
            'platform', 'product', 'logo'
        ]
        
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        task_id = str(uuid.uuid4())
        
        # Create new session
        session_manager.create_session(task_id, data)
        
        task_status[task_id] = {
            'overall_status': 'processing',
            'content_status': 'processing',
            'image_status': 'processing'
        }
        task_results[task_id] = {}
        
        Thread(target=process_request_async, args=(task_id, data)).start()
        
        return jsonify({
            'task_id': task_id,
            'status': 'processing'
        }) 
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/regenerate-content', methods=['POST'])
def regenerate_content():
    try:
        data = request.json
        if 'task_id' not in data:
            return jsonify({'error': 'Missing task_id'}), 400
            
        original_task_id = data['task_id']
        session = session_manager.get_session(original_task_id)
        
        if not session:
            return jsonify({'error': 'Session expired or not found'}), 404
        
        # Use original data from session
        original_data = session.original_data.copy()
        
        # Update with any new data provided
        for key in data:
            if key != 'task_id':
                original_data[key] = data[key]
        
        new_task_id = str(uuid.uuid4())
        session.task_ids.append(new_task_id)
        
        task_status[new_task_id] = {
            'overall_status': 'processing',
            'content_status': 'processing',
            'image_status': 'not_started'  # Changed to not_started
        }
        task_results[new_task_id] = {}
        
        Thread(target=process_content_only, args=(new_task_id, original_data)).start()
        
        return jsonify({
            'task_id': new_task_id,
            'status': 'processing'
        })
    
    except Exception as e:
        logger.error(f"Error regenerating content: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/regenerate-image', methods=['POST'])
def regenerate_image():
    try:
        data = request.json
        if 'task_id' not in data:
            return jsonify({'error': 'Missing task_id'}), 400
            
        original_task_id = data['task_id']
        session = session_manager.get_session(original_task_id)
        
        if not session:
            return jsonify({'error': 'Session expired or not found'}), 404
        
        new_task_id = str(uuid.uuid4())
        session.task_ids.append(new_task_id)
        
        # Use original data but update logo if provided
        regeneration_data = session.original_data.copy()
        if 'logo' in data:
            regeneration_data['logo'] = data['logo']
        
        # Copy existing content
        original_content = task_results[original_task_id].get('content')
        if not original_content:
            return jsonify({'error': 'Original content not found'}), 404
        
        task_status[new_task_id] = {
            'overall_status': 'processing',
            'content_status': 'not_started',  # Changed to
# 'content_status': 'not_started',  # Changed to not_started
            'image_status': 'processing'
        }
        task_results[new_task_id] = {
            'content': original_content
        }
        
        Thread(target=process_image_only, args=(new_task_id, regeneration_data, original_content)).start()
        
        return jsonify({
            'task_id': new_task_id,
            'status': 'processing'
        })
    
    except Exception as e:
        logger.error(f"Error regenerating image: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/check-status/<task_id>', methods=['GET'])
def check_status(task_id):
    """Check the status of a task"""
    if task_id not in task_status:
        return jsonify({'error': 'Task not found'}), 404
        
    status = task_status[task_id]
    session = session_manager.get_session(task_id)
    
    if status['overall_status'] == 'completed':
        result = task_results[task_id]
        # Don't delete task results if it's part of an active session
        if not session:
            if task_id in task_status:
                del task_status[task_id]
            if task_id in task_results:
                del task_results[task_id]
        return jsonify({
            'status': 'completed',
            'result': result
        })
    elif status['overall_status'] == 'failed':
        error = status.get('error', 'Unknown error')
        if not session:
            if task_id in task_status:
                del task_status[task_id]
            if task_id in task_results:
                del task_results[task_id]
        return jsonify({
            'status': 'failed',
            'error': error
        })
    else:
        return jsonify({
            'status': 'processing',
            'progress': status
        })

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"Route not found: {str(error)}")
    return jsonify({'error': 'Route not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000)            