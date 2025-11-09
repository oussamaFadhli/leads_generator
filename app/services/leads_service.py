import json
from sqlalchemy.orm import Session
from scrapegraphai.graphs import SearchGraph
from app.core.config import settings
from app.models import models
from app.crud import crud
from app.schemas import schemas
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def perform_leads_search(saas_info_id: int, db: Session):
    logging.info(f"--- Entering perform_leads_search for SaaS Info ID: {saas_info_id} ---")
    logging.info(f"Starting lead search for SaaS Info ID: {saas_info_id}")
    saas_info_db = crud.get_saas_info(db, saas_info_id)
    if not saas_info_db:
        logging.error(f"SaaS Info with ID {saas_info_id} not found.")
        return

    # Convert SQLAlchemy model to a dictionary for the prompt
    saas_info_dict = {
        "name": saas_info_db.name,
        "one_liner": saas_info_db.one_liner,
        "features": [{"name": f.name, "desc": f.description} for f in saas_info_db.features],
        "pricing": [{"plan_name": p.plan_name, "price": p.price, "features": json.loads(p.features) if p.features else [], "link": p.link} for p in saas_info_db.pricing],
        "target_segments": json.loads(saas_info_db.target_segments) if saas_info_db.target_segments else []
    }
    logging.info(f"SaaS Info Dict for prompt: {json.dumps(saas_info_dict, indent=2)}")

    prompt_dict = f"""
    Based on the following SaaS project information, search the internet for:
    1. A famous competitor: Identify a key competitor in the market.
    2. Strengths and Weaknesses: For this competitor, list their main strengths and weaknesses.
    3. Related Subreddits: Find the best subreddits related to the project's interests.

    SaaS Project Information:
    {json.dumps(saas_info_dict, indent=2)}

    IMPORTANT: Return the output as a JSON object with the following structure:
    {{
        "competitor_name": "Name of the competitor",
        "strength": "Main strengths of the competitor",
        "weakness": "Main weaknesses of the competitor",
        "related_subreddits": ["subreddit1", "subreddit2", "subreddit3"]
    }}

    Return ONLY the JSON object, no additional text or markdown formatting.
    """

    graph_config = {
        "llm": {
            "api_key": settings.NVIDIA_KEY,
            "model": "nvidia/mistralai/mistral-nemotron",
            "temperature": 0,
            "format": "json",
        },
        "max_results": 7,
        "loader_kwargs": {"slow_mo": 10000},
        "verbose": True,
        "headless": True,
    }

    search_graph = SearchGraph(
        prompt=prompt_dict, config=graph_config
    )

    try:
        raw_output = search_graph.run()
        logging.info(f"Lead search completed for SaaS Info ID: {saas_info_id}")
        logging.info(f"Raw output from search_graph.run(): {raw_output}")
        logging.info(f"Raw output type: {type(raw_output)}")

        processed_result = None
        
        # Handle string output
        if isinstance(raw_output, str):
            try:
                processed_result = json.loads(raw_output)
                logging.info(f"Parsed JSON from string. Result type: {type(processed_result)}")
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse SearchGraph result as JSON: {e}")
                logging.error(f"Raw output was: {raw_output}")
                return
        else:
            processed_result = raw_output
            logging.info(f"Using raw output directly. Type: {type(processed_result)}")

        # Log the structure of processed_result
        if isinstance(processed_result, list):
            logging.info(f"Processed result is a list with {len(processed_result)} items")
            if len(processed_result) > 0:
                logging.info(f"First item type: {type(processed_result[0])}")
                logging.info(f"First item: {processed_result[0]}")
        elif isinstance(processed_result, dict):
            logging.info(f"Processed result is a dict with keys: {processed_result.keys()}")
        
        # Normalize the result into a list of lead dictionaries
        leads_to_process = []
        
        if isinstance(processed_result, dict):
            # Check if it's a wrapper with a 'leads' key
            if "leads" in processed_result:
                leads_to_process = processed_result["leads"]
                logging.info("Found 'leads' key in dict, extracting list")
            # Check if it's a single lead object
            elif "competitor_name" in processed_result and "related_subreddits" in processed_result:
                leads_to_process = [processed_result]
                logging.info("Dict appears to be a single lead, wrapping in list")
            else:
                logging.error(f"Dict doesn't match expected format. Keys: {processed_result.keys()}")
                return
        elif isinstance(processed_result, list):
            # Check if list items are dicts or something else
            if len(processed_result) > 0:
                if isinstance(processed_result[0], dict):
                    leads_to_process = processed_result
                    logging.info("List contains dicts, using directly")
                else:
                    logging.error(f"List items are not dicts. First item type: {type(processed_result[0])}")
                    logging.error(f"First item value: {processed_result[0]}")
                    return
            else:
                logging.warning("Received empty list from SearchGraph")
                return
        else:
            logging.error(f"Unexpected format: {type(processed_result)}")
            return

        logging.info(f"Processing {len(leads_to_process)} leads")

        # Process each lead
        for idx, lead_item in enumerate(leads_to_process):
            logging.info(f"Processing lead {idx + 1}/{len(leads_to_process)}")
            logging.info(f"Lead item type: {type(lead_item)}")
            logging.info(f"Lead item: {lead_item}")
            
            if not isinstance(lead_item, dict):
                logging.error(f"Lead item is not a dict: {type(lead_item)} - {lead_item}")
                continue
                
            # Validate required fields
            required_fields = ["competitor_name", "related_subreddits"]
            missing_fields = [f for f in required_fields if f not in lead_item]
            
            if missing_fields:
                logging.error(f"Lead item missing required fields: {missing_fields}")
                logging.error(f"Available keys: {lead_item.keys()}")
                continue
            
            try:
                lead_data = lead_item.copy()
                
                # Remove 'sources' as it's not part of the LeadCreate schema
                lead_data.pop("sources", None)
                
                # Ensure related_subreddits is a list
                if isinstance(lead_data.get("related_subreddits"), str):
                    try:
                        lead_data["related_subreddits"] = json.loads(lead_data["related_subreddits"])
                    except json.JSONDecodeError:
                        logging.error(f"Could not parse related_subreddits as JSON: {lead_data['related_subreddits']}")
                        continue

                logging.info(f"Creating lead with data: {lead_data}")
                lead_schema = schemas.LeadCreate(**lead_data)
                created_lead = crud.create_lead(db, lead_schema, saas_info_id)
                logging.info(f"Successfully created lead with ID: {created_lead.id if hasattr(created_lead, 'id') else 'unknown'}")
                
            except Exception as e:
                logging.error(f"Error validating or creating lead: {e}")
                logging.error(f"Lead data was: {lead_data}")
                import traceback
                logging.error(f"Traceback: {traceback.format_exc()}")

    except Exception as e:
        logging.error(f"Error during lead search for SaaS Info ID {saas_info_id}: {e}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")