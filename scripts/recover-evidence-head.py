"""Preview legacy head recovery; --apply requires explicit operator intent."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from services.dynamodb import DynamoDBService

parser = argparse.ArgumentParser()
parser.add_argument("customer_id")
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()
print(json.dumps(DynamoDBService().recover_evidence_head(args.customer_id, apply=args.apply)))
