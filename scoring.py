import re
from langchain.chat_models import init_chat_model


def check_documentation_quality(file_content, file_type="nextflow"):
    """Use AI to analyze documentation quality and return a score"""
    model = init_chat_model("gemini-3-flash-preview", model_provider="google_genai")

    if file_type == "nextflow":
        prompt = f"""
        Please analyze this Nextflow pipeline file for quality and accuracy:

        {file_content[:6000]}  # Limit content to avoid token limits

        Check for:
        1. Are all parameters documented?
        2. Are parameter types clearly specified?
        3. Are default values appropriate?
        4. Are required vs optional parameters clearly marked?
        5. Is the usage information clear?
        6. Are there any inconsistencies or errors?

        Provide a concise, structured report and include a numerical score out of 10 at the end.
        Format your response as:

        ANALYSIS:
        [Your detailed analysis here]

        SCORE: [number]/10

        Do not provide any specific recommendations.
        """
    elif file_type == "config":
        prompt = f"""
        Please analyze this Nextflow configuration file for quality and accuracy:

        {file_content[:6000]}

        Check for:
        1. Are all configuration options properly documented?
        2. Are default values appropriate and well-explained?
        3. Are there clear comments explaining complex configurations?
        4. Is the configuration structure logical and organized?
        5. Are there any deprecated or incorrect configurations?

        Provide a concise, structured report and include a numerical score out of 10 at the end. If an external wiki is referenced, please consider this positively with a maximum score boost of one point.
        Format your response as:

        ANALYSIS:
        [Your detailed analysis here]

        SCORE: [number]/10

        Do not provide any specific recommendations.
        """
    elif file_type == "readme":
        prompt = f"""
        Please analyze this README file for quality and completeness:

        {file_content[:6000]}

        Check for:
        1. Is the installation process clearly explained?
        2. Are usage examples provided and working?
        3. Are all parameters and options documented?
        4. Is there troubleshooting information?
        5. Are dependencies and requirements clearly stated?
        6. Is the documentation up-to-date and accurate?

        Provide a concise, structured report and include a numerical score out of 10 at the end. If an external wiki is referenced, please consider this positively with a maximum score boost of one point.
        Format your response as:

        ANALYSIS:
        [Your detailed analysis here]

        SCORE: [number]/10

        Do not provide any specific recommendations.
        """
    else:
        prompt = f"""
        Please analyze this documentation for quality and accuracy:

        {file_content[:6000]}

        Check for:
        1. Clarity and completeness
        2. Accuracy of technical information
        3. Missing or outdated information
        4. Consistency issues

        Provide a concise, structured report and include a numerical score out of 10 at the end. If an external wiki is referenced, please consider this positively with a maximum score boost of one point.
        Format your response as:

        ANALYSIS:
        [Your detailed analysis here]

        SCORE: [number]/10

        Do not provide any specific recommendations.
        """

    response = model.invoke([{"role": "user", "content": prompt}])
    return response.content


def extract_score_from_response(response_text):
    """Extract numerical score from AI response"""
    try:
        # Look for "SCORE: X/10" pattern
        score_match = re.search(r'SCORE:\s*(\d+(?:\.\d+)?)/10', response_text, re.IGNORECASE)
        if score_match:
            score = float(score_match.group(1))
            return min(max(score, 0), 10)  # Ensure score is between 0 and 10

        # Fallback: look for any number followed by /10
        score_match = re.search(r'(\d+(?:\.\d+)?)/10', response_text)
        if score_match:
            score = float(score_match.group(1))
            return min(max(score, 0), 10)

        # If no score found, return 0 as default
        return 0.0
    except (ValueError, AttributeError):
        return 0.0


def calculate_overall_score(all_reports):
    """Calculate overall score out of 10 based on all reports."""
    if not all_reports:
        return 0.0

    total_score = 0
    num_files = len(all_reports)

    for file_path, report in all_reports.items():
        ai_score = extract_score_from_response(report['quality_report'])
        weighted_score = ai_score

        # Add parameter coverage bonus for pipeline files
        if report['type'] in ("nextflow", "snakemake", "cwl", "wdl") and report['params']:
            coverage = len(report['param_docs']) / len(report['params'])
            coverage_bonus = coverage * 2  # Up to 2 points bonus
            weighted_score = min(weighted_score + coverage_bonus, 10)

        total_score += weighted_score

    overall_score = total_score / num_files if num_files > 0 else 0
    return round(overall_score, 1)
