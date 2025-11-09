"""
depth_search_graph_opeani example
"""

import os
import json

from dotenv import load_dotenv

from scrapegraphai.graphs import DepthSearchGraph
from schema.saas_schema import SaaSInfo
load_dotenv()

nvidia_key = os.getenv("NVIDIA_KEY")

graph_config = {
    "llm": {
        "api_key": nvidia_key,
        "model": "nvidia/mistralai/mistral-nemotron",
        "temperature": 0,
        "format": "json", 
    },
    "verbose": True,
    "headless": True,
    "depth": 1,
    "only_inside_links": False,
}

enhanced_prompt = """
{
  "instruction": "Extract comprehensive information about the SaaS product from the given website. Ensure all extracted data strictly conforms to the SaaSInfo Pydantic model schema.",
  "fields_to_extract": {
    "name": "The official name of the SaaS product.",
    "one_liner": "A concise, single-sentence description of what the SaaS product does.",
    "features": [
      {
        "name": "The name of a specific feature.",
        "desc": "A detailed description of that feature."
      }
    ],
    "pricing": [
      {
        "plan_name": "The name of the pricing plan (e.g., 'Basic', 'Pro', 'Enterprise').",
        "price": "The cost of the plan (e.g., '$10/month', 'Free', 'Contact Us').",
        "features": "A list of key features included in this specific pricing plan.",
        "link": "An optional URL to the pricing plan's details or signup page."
      }
    ],
    "target_segments": "A list of target customer segments or industries the SaaS product is designed for (e.g., 'Small Businesses', 'Developers', 'Healthcare')."
  },
  "output_format": "JSON, strictly adhering to the SaaSInfo Pydantic model structure."
}
"""

search_graph = DepthSearchGraph(
    prompt=enhanced_prompt,
    source="https://www.trucking88.com",
    schema=SaaSInfo,
    config=graph_config,
)

result = search_graph.run()

# Save the result to a JSON file
output_file = "saas_info.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=4)

print(f"Result saved to {output_file}")
