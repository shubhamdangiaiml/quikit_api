from flask import Flask, request, jsonify
import google.generativeai as genai
import json
import requests
from PIL import Image
import io
from datetime import datetime
import base64
import random
import time
import logging
import os
from flask_cors import CORS


import random
import base64
# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

API_URL_FLUX = ""
API_URL_Midjourney = ""
HF_HEADERS = {""}
genai.configure(api_key='')


# def generate_marketing_content(input_data, product):
#     """Generate marketing content using Gemini model"""
#     try:
#         model = genai.GenerativeModel('gemini-1.5-flash')
        
#         input_prompt = f"""
#             You are an expert in generating marketing content.
#             Generate unique marketing content for the following:
#             - **Company Name**: {input_data['company_name']}
#             - **Business Domain**: {input_data['business_domain']}
#             - **Specific Focus**: {input_data['specific_focus']}
#             - **Target Audience**: {input_data['target_audience']}
#             - **Key Features**: {input_data['key_features']}
#             - **Unique Selling Points**: {input_data['unique_selling_points']}
#             - **Pricing & Packages**: {input_data['pricing_packages']}
#             - **Target Platform**: {input_data['target_platform']}
#             - **Product/Service**: {product}

#             **Requirements**:
#             - Title (short and engaging)
#             - Punchline (attention-grabbing one-liner)
#             - 125-word Content (focused on the product)
#             - 5 relevant hashtags
#             - 5 keywords for image generation
#             Note-For Twitter platform please ensure that Full content must be below 250 caracters keep it short dont give any link with this 
#             Response must be in **JSON format** with keys: "Title", "Punchline", "Content", "Hashtags", "Keywords".
#         """
        
#         completion = model.generate_content([input_prompt])
#         response_text = completion.text.strip()
        
#         if response_text.startswith('```json'):
#             response_text = response_text.replace('```json', '').strip()
#             if response_text.endswith('```'):
#                 response_text = response_text[:-3].strip()
        
#         return json.loads(response_text)
    
#     except Exception as e:
#         logger.error(f"Error generating marketing content: {str(e)}")
#         raise
def generate_marketing_content(input_data, product):
    """Generate platform-specific marketing content using Gemini model"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        platform_constraints = {
            "Twitter": "Ensure the full content is below 250 characters.",
            "LinkedIn": "Content should be professional and detailed (up to 125 words).",
            "Instagram": "Make the content engaging.",
            "Facebook": "Create balanced content suitable for a broad audience.",
    
        }
        
        target_platform = input_data['target_platform']
        constraint = platform_constraints.get(target_platform, "Ensure content is engaging and effective.")

        input_prompt = f"""
            You are an expert in generating platform-specific marketing content.
            Generate unique marketing content based on the following details:
            - **Company Name**: {input_data['company_name']}
            - **Business Domain**: {input_data['business_domain']}
            - **Specific Focus**: {input_data['specific_focus']}
            - **Target Audience**: {input_data['target_audience']}
            - **Key Features**: {input_data['key_features']}
            - **Unique Selling Points**: {input_data['unique_selling_points']}
            - **Pricing & Packages**: {input_data['pricing_packages']}
            - **Target Platform**: {target_platform}
            - **Product/Service**: {product}

            **Platform-Specific Constraint**: {constraint}

            **Content Requirements**:
            - Title (short and engaging)
            - Punchline (attention-grabbing one-liner)
            - Platform-optimized content
            - 5 relevant hashtags
            
            Important: Avoid using any special characters like *, _, or other markdown symbols. Provide plain text only and ensure did'nt give any link or suggestion .
            Response must be in **JSON format** with keys: "Title", "Punchline", "Content", "Hashtags", "Keywords".

            "
        """ 
        
        completion = model.generate_content([input_prompt])
        response_text = completion.text.strip()
        
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').strip()
            if response_text.endswith('```'):
                response_text = response_text[:-3].strip()
        print("1111111111111111111111111111111111111111111111111111111111111",response_text)
        return json.loads(response_text)
    
    except Exception as e:
        logger.error(f"Error generating marketing content: {str(e)}")
        raise

@app.route('/generate-marketing-content', methods=['POST'])
def generate_content():
    try:
        data = request.json
        required_fields = [
            'company_name', 'business_domain', 'specific_focus', 'target_audience',
            'key_features', 'unique_selling_points', 'pricing_packages',
            'target_platform', 'products', 'days', 'logo'
        ]
        
        # Validate input
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        products = [p.strip() for p in data['products'].split(",") if p.strip()]
        total_days = int(data['days'])
        
        if len(products) == 0:
            logger.error("No products provided")
            return jsonify({'error': 'Please provide at least one product or service'}), 400
        
        # Generate content for each day
        content_results = []
        for day in range(1, total_days + 1):
            logger.info(f"Generating content for day {day}")
            product = products[day - 1] if day <= len(products) else random.choice(products)
            
            # Generate marketing content
            generated_content = generate_marketing_content(data, product)

            
            # Generate image with retriesb
  

            def random_image_to_base64(folder_path):
                """
                Select a random image from the given folder, convert it to Base64, and return the encoded string.

                Args:
                    folder_path (str): Path to the folder containing images.

                Returns:
                    str: Base64 encoded string of the image content.
                """
                # List all files in the folder
                images = [file for file in os.listdir(folder_path) if file.lower().endswith(('png', 'jpg', 'jpeg', 'gif'))]
                
                if not images:
                    raise ValueError("No images found in the specified folder.")
                
                # Select a random image
                random_image = random.choice(images)
                image_path = os.path.join(folder_path, random_image)
                
                # Convert the image to Base64
                with open(image_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                
                return encoded_string

            # Example usage
            folder_path = "images"  # Replace with the path to your image folder
            try:
                image_base64 = random_image_to_base64(folder_path)
                print("Image successfully encoded to Base64.")
            except ValueError as e:
                print(e)
                                

                
            add_string='data:image/jpeg;base64,'
            # Prepare response
            day_content = {
                'day': day,
                'content': generated_content,
                'image': add_string+image_base64
                # 'image_status': 'success' if image_base64 else 'failed'
            }
            content_results.append(day_content)
            
            # Add delay between requests to avoid rate limiting
            if day < total_days:
                time.sleep(2)
        
        logger.info("Content generation completed successfully")
        return jsonify({
            'success': True,
            'generated_content': content_results
        })
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return jsonify({'error': 'Invalid JSON response from content generation'}), 500
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"Route not found: {str(error)}")
    return jsonify({'error': 'Route not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)