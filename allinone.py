from flask import Flask, request, jsonify
import google.generativeai as genai
import json
import logging
import os
from flask_cors import CORS
import random
import base64
import time

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

genai.configure(api_key='AIzaSyB9YriqATKbxNWoeeRh8EGmiMztrAIGtJ4')

def generate_platform_specific_content(input_data, product, platform):
    """Generate platform-specific marketing content using Gemini model"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        platform_specific_prompts = {
            "facebook": """
                Generate Facebook-specific marketing content with:
                - Engaging post (200-250 characters)
                - Call-to-action
                - 3-5 relevant hashtags
                - Keywords for image generation
            """,
            "instagram": """
                Generate Instagram-specific marketing content with:
                - Catchy caption (150-200 characters)
                - Emojis
                - 5-7 trending hashtags
                - Keywords for image generation
            """,
            "linkedin": """
                Generate LinkedIn-specific marketing content with:
                - Professional post (300-350 characters)
                - Industry-specific insights
                - 3-4 relevant hashtags
                - Keywords for image generation
            """,
            "twitter": """
                Generate Twitter-specific marketing content with:
                - Tweet (maximum 100 characters)
                - Engaging hook
                - 2-3 trending hashtags
                - Keywords for image generation
            """
        }

        input_prompt = f"""
            You are an expert in generating platform-specific marketing content.
            Generate unique marketing content for:
            - **Company Name**: {input_data['company_name']}
            - **Business Domain**: {input_data['business_domain']}
            - **Specific Focus**: {input_data['specific_focus']}
            - **Target Audience**: {input_data['target_audience']}
            - **Key Features**: {input_data['key_features']}
            - **Unique Selling Points**: {input_data['unique_selling_points']}
            - **Pricing & Packages**: {input_data['pricing_packages']}
            - **Product/Service**: {product}

            {platform_specific_prompts.get(platform.lower(), "")}

            Response must be in JSON format with keys: "content", "hashtags", "keywords".
        """
        
        completion = model.generate_content([input_prompt])
        response_text = completion.text.strip()
        
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').strip()
            if response_text.endswith('```'):
                response_text = response_text[:-3].strip()
        
        return json.loads(response_text)
    
    except Exception as e:
        logger.error(f"Error generating content for {platform}: {str(e)}")
        raise

def random_image_to_base64(folder_path):
    """Select a random image from the given folder and convert it to Base64"""
    try:
        images = [file for file in os.listdir(folder_path) if file.lower().endswith(('png', 'jpg', 'jpeg', 'gif'))]
        if not images:
            raise ValueError("No images found in the specified folder.")
        
        random_image = random.choice(images)
        image_path = os.path.join(folder_path, random_image)
        
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Error in image processing: {str(e)}")
        return None

@app.route('/generate-marketing-content', methods=['POST'])
def generate_content():
    try:
        data = request.json
        required_fields = [
            'company_name', 'business_domain', 'specific_focus', 'target_audience',
            'key_features', 'unique_selling_points', 'pricing_packages',
            'platforms', 'products', 'days', 'logo'
        ]
        
        # Validate input
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        products = [p.strip() for p in data['products'].split(",") if p.strip()]
        platforms = [p.strip().lower() for p in data['platforms'].split(",") if p.strip()]
        total_days = int(data['days'])
        
        if not products:
            logger.error("No products provided")
            return jsonify({'error': 'Please provide at least one product or service'}), 400
        
        if not platforms:
            logger.error("No platforms provided")
            return jsonify({'error': 'Please provide at least one platform'}), 400
        
        # Generate content for each day
        content_results = []
        for day in range(1, total_days + 1):
            logger.info(f"Generating content for day {day}")
            product = products[day - 1] if day <= len(products) else random.choice(products)
            
            # Generate platform-specific content
            platform_content = {}
            for platform in platforms:
                platform_content[platform] = generate_platform_specific_content(data, product, platform)
            
            # Get random image
            image_base64 = random_image_to_base64("images")
            
            # Prepare response
            day_content = {
                'day': day,
                'product': product,
                'platform_content': platform_content,
                'image': f'data:image/jpeg;base64,{image_base64}' if image_base64 else None
            }
            content_results.append(day_content)
            
            # Add delay between requests
            if day < total_days:
                time.sleep(2)
        
        logger.info("Content generation completed successfully")
        return jsonify({    
            'success': True,
            'generated_content': content_results
        })
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': str(e)}), 500




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)