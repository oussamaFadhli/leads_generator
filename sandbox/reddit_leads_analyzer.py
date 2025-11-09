import json
import os
from dotenv import load_dotenv

from scrapegraphai.graphs import DocumentScraperGraph
from schema.reddit_leads_schema import RedditLeadsAnalysisResult, ScoredRedditPost

load_dotenv()
nvidia_key = os.getenv("NVIDIA_KEY")

# ************************************************
# Define the configuration for the graph
# ************************************************
graph_config = {
    "llm": {
        "api_key": nvidia_key,
        "model": "nvidia/mistralai/mistral-nemotron",
        "temperature": 0,
        "format": "json",
        "model_tokens": 4000,
    },
    "verbose": True,
    "headless": False,
}

def load_json_file(filepath):
    """Loads a JSON file from the given filepath."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    saas_info = load_json_file('saas_info.json')
    reddit_posts = load_json_file('reddit_posts.json')

    # Combine saas_info and reddit_posts into a single string source for the AI
    source_content = f"SaaS Information:\n{json.dumps(saas_info, indent=2)}\n\nReddit Posts:\n{json.dumps(reddit_posts, indent=2)}"

    prompt = """
    Analyze the provided SaaS Information and Reddit Posts.
    Identify which Reddit posts represent high-quality leads for the SaaS product.
    A high-quality lead is a Reddit post where the user expresses a problem or need that can be directly addressed by the SaaS product's features, one-liner, or targets segments.
    Consider the SaaS product's name, one-liner, features (name and description), and target segments.
    For each identified lead, provide a 'lead_score' (a numerical value indicating the strength of the match) and a 'score_justification' (a brief explanation of why it's a good lead, referencing specific SaaS features or target segments and post content).
    Order the leads by 'lead_score' in descending order.
    The output MUST strictly conform to the JSON schema defined by the `RedditLeadsAnalysisResult` Pydantic model.
    The output should be a JSON object with a single key "top_leads" which is a list of `ScoredRedditPost` objects.
    Each `ScoredRedditPost` object must include all original fields of the Reddit post (title, content, score, num_comments, author, url, subreddit) plus "lead_score" (float) and "score_justification" (string).
    If no relevant leads are found, return an empty list for "top_leads".
    """

    document_scraper_graph = DocumentScraperGraph(
        prompt=prompt,
        source=source_content,
        schema=RedditLeadsAnalysisResult, # Use the imported Pydantic schema
        config=graph_config,
    )

    result = document_scraper_graph.run()

    valid_leads = []
    # The AI might return a dictionary with 'top_leads' or directly a list of posts.
    # We need to handle both cases and ensure 'top_leads' is a list.
    if isinstance(result, dict) and "top_leads" in result and isinstance(result["top_leads"], list):
        raw_leads = result["top_leads"]
    elif isinstance(result, list):
        raw_leads = result
    else:
        print("AI output did not contain a 'top_leads' list or was not in expected dictionary/list format.")
        print("AI output:", result)
        raw_leads = []

    for item in raw_leads:
        try:
            # Attempt to validate each item as a ScoredRedditPost
            validated_post = ScoredRedditPost.model_validate(item)
            valid_leads.append(validated_post)
        except Exception as e:
            print(f"Skipping malformed lead due to validation error: {e}")
            print("Malformed item:", item)

    # Create the final output data using the validated leads
    output_data = RedditLeadsAnalysisResult(top_leads=valid_leads).model_dump(mode='json')

    # Output to top_reddit_leads.json
    with open('top_reddit_leads.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)

    print("Top Reddit leads generated and saved to 'top_reddit_leads.json'")

if __name__ == "__main__":
    main()
