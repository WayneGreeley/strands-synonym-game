"""Simple test Lambda handler."""

import json


def lambda_handler(event, context):
    """Simple test handler."""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'message': 'Hello from SynonymSeeker!'})
    }