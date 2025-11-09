import json
import os
from dotenv import load_dotenv

from scrapegraphai.graphs import DocumentScraperGraph
from schema.generated_post_schema import GeneratedPostsResult, GeneratedPost

load_dotenv()
nvidia_key = os.getenv("NVIDIA_KEY")

# ************************************************
# Define the configuration for the graph
# ************************************************
graph_config = {
    "llm": {
        "api_key": nvidia_key,
        "model": "nvidia/mistralai/mistral-nemotron",
        "temperature": 0.7, 
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
    top_leads = load_json_file('top_reddit_leads.json')

    generated_posts = []

    for lead in top_leads.get("top_leads", []):
        source_content = f"SaaS Information:\n{json.dumps(saas_info, indent=2)}\n\nOriginal Reddit Post:\n{json.dumps(lead, indent=2)}"

        prompt = f"""
        Based on the provided SaaS information and the original Reddit post, generate a new, similar Reddit post.
        The new post should be written in a human-like, friendly, and youthful tone, suitable for Reddit. It should not sound like a generic AI.
        The post should address the core problem or topic of the original post, but from a new perspective.
        Subtly hint at a solution related to the '{saas_info['name']}' SaaS product without being an obvious advertisement.
        The output MUST strictly conform to the JSON schema defined by the `GeneratedPost` Pydantic model.
        The output should be a JSON object with 'original_post_url', 'title', and 'content' fields.
        """

        document_scraper_graph = DocumentScraperGraph(
            prompt=prompt,
            source=source_content,
            schema=GeneratedPost,
            config=graph_config,
        )

        result = document_scraper_graph.run()

        if result:
            try:
                validated_post = GeneratedPost.model_validate(result)
                generated_posts.append(validated_post)
            except Exception as e:
                print(f"Skipping malformed post due to validation error: {e}")
                print("Malformed item:", result)

    output_data = GeneratedPostsResult(generated_posts=generated_posts).model_dump(mode='json')

    with open('generated_reddit_posts.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)

    print("Generated Reddit posts saved to 'generated_reddit_posts.json'")

if __name__ == "__main__":
    main()
