import logging
import time
import praw

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_account_health(reddit: praw.Reddit) -> bool:
    """Check if the Reddit account is in good standing."""
    try:
        user = reddit.user.me()
        karma = user.link_karma + user.comment_karma
        account_age_days = (time.time() - user.created_utc) / 86400
        
        logging.info(f"Account: u/{user.name}")
        logging.info(f"Total Karma: {karma}")
        logging.info(f"Account Age: {account_age_days:.1f} days")
        logging.info(f"Verified Email: {user.has_verified_email}")
        
        if karma < 50:
            logging.warning("⚠️ Low karma account - high spam detection risk")
        if account_age_days < 7:
            logging.warning("⚠️ New account - high spam detection risk")
        if not user.has_verified_email:
            logging.warning("⚠️ Email not verified - posts may be auto-removed")
            
        return True
    except Exception as e:
        logging.error(f"Failed to check account health: {e}")
        return False
