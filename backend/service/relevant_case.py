import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import time # To measure embedding time

# --- Configuration ---
# Choose a sentence transformer model
# 'all-MiniLM-L6-v2' is a good starting point: fast and decent quality.
# Other options: 'all-mpnet-base-v2' (better quality, slower), 'multi-qa-mpnet-base-dot-v1' (good for QA)
MODEL_NAME = 'all-MiniLM-L6-v2'
import requests


def get_embedding(text):
    url = "https://api.rabbithole.cred.club/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-AGQNqGuzxAULwPC9ay5Gug"
    }
    data = {
        "model": "text-embedding-3-large",
        "input": "hello"
    }

    response = requests.post(url, json=data, headers=headers)

    output = response.json()['data'][0]['embedding']  # Print the response JSON
    return output


import time
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from pymongo.collection import Collection # Import Collection for type hinting
from bson import ObjectId # Might be needed if you work directly with ObjectIds

# Assume 'model' is already loaded, e.g.:
# model = SentenceTransformer('all-MiniLM-L6-v2')

# Assume 'client' and 'db' are established, and 'collection' is passed in:
# import pymongo
# client = pymongo.MongoClient("mongodb://localhost:27017/") # Or your connection string
# db = client["landmark_judgments_db"]
# landmark_collection = db["landmark_judgments"]
def get_sections_involved(judgment_summary):
    prompt = f"""what all section and act involved in this case. give me only list of act only nothing else. while giving me act use their proper name according to indian court and law system
    {judgment_summary}"""
    url = "https://api.rabbithole.cred.club/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-AGQNqGuzxAULwPC9ay5Gug"
    }
    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}]
    }

    response = requests.post(url, json=data, headers=headers)

    output = response.json()  # Print the response JSON
    return output['choices'][0]['message']['content']


def get_sections_involved(section_string, user_query_section):
    prompt = f"""Given section_string  that contain serial number and sections involved in a case.
    also suer_quer that also contain sections involved. now i want you to give me all serial number 
    that contain same sections involved as in user_query.
    SECTION_STRING:
    - {section_string}
    USER_QUERY:
    - {user_query_section}
    OUTPUT format  should be like this:
    [2,4,6]. strickly follow this format.
    OUTPUT:
    """
    url = "https://api.rabbithole.cred.club/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-AGQNqGuzxAULwPC9ay5Gug"
    }
    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}]
    }

    response = requests.post(url, json=data, headers=headers)

    output = response.json()  # Print the response JSON
    output=  output['choices'][0]['message']['content']
    output = output.replace("[", "").replace("]", "").replace(" ", "").split(",")
    return output

def get_relvenat_case(case_list, user_query_section):
    prompt = f"""Given are given list of cases CASE_LIST with their sections involved. and their case summary. 
    also a user query. i want you to give me all the cases which you think are relevant to the user query.
    make sure you involve cases that are most relevant to the user query.
    CASE_LIST:
    - {case_list}
    USER_QUERY:
    - {user_query_section}
    in response you can give that case detail with a small summary of that case that you think are related to
    given user query.
    """
    url = "https://api.rabbithole.cred.club/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-AGQNqGuzxAULwPC9ay5Gug"
    }
    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}]
    }

    response = requests.post(url, json=data, headers=headers)

    output = response.json()  # Print the response JSON
    output=  output['choices'][0]['message']['content']
    output = output.replace("[", "").replace("]", "").replace(" ", "").split(",")
    return output


def search_documents_mongodb(
    # request, # Keep if used in a web framework context, otherwise optional
    query: str, # Pass the MongoDB collection object
):
    """
    Searches documents stored in a MongoDB collection based on semantic similarity.

    1. Fetches document embeddings and identifiers from MongoDB.
    2. Generates the embedding for the user query.
    3. Calculates cosine similarity between the query embedding and all document embeddings.
    4. Retrieves the top_k full documents from MongoDB based on similarity scores.

    Args:
        query (str): The user's search query.
        collection (Collection): The pymongo Collection object containing the indexed documents.
                                 Expected document structure: {"text": str, "metadata": dict, "embedding": list, "_id": ObjectId}.
        model (SentenceTransformer): The loaded sentence transformer model.
        top_k (int): The number of top results to return.

    Returns:
        list: A list of dictionaries, each containing a matching 'document' (with text and metadata)
              and its similarity 'score'. Returns an empty list if no documents are found or an error occurs.
    """
    import pymongo
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017/")

    # Access a specific database (create if it doesn't exist)
    db = client["landmark_judgments_db"]

    # Access a specific collection (create if it doesn't exist)
    collection = db["landmark_judgments"]
    print(f"\nSearching for query: '{query}' in MongoDB collection '{collection.name}'")

    # --- 1. Fetch document embeddings and IDs from MongoDB ---
    print("Fetching document embeddings from MongoDB...")
    start_time = time.time()
    try:
        # Fetch only the necessary fields: _id and embedding
        # Using a cursor to potentially handle large collections better
        cursor = collection.find({}, {"_id": 1, "embedding": 1})

        doc_data = []
        section_string = []

        for doc in cursor:
            if "metadata" in doc and "_id" in doc:
                 # Ensure embedding is a list/iterable of numbers
                 section_string.append("Serial Number:" + doc["metadata"]['Serial Number'] + "sections_involved: "+ doc["metadata"]['sections_involved'])
            else:
                print(f"Warning: Document {doc.get('_id', 'Unknown ID')} is missing _id or embedding. Skipping.")

        # Extract embeddings and corresponding IDs
        my_query_section = get_sections_involved(query)

        get_serial_number = get_serial_number(section_string, my_query_section)

        doc_data = []
        for doc in cursor:
            if doc["metadata"]['Serial Number'] in get_serial_number:
                doc_data.append(doc)

        response = get_relvenat_case(doc_data, query)
        return response

    except Exception as e:
        print(f"Error fetching embeddings from MongoDB: {e}")
        return []
        return results
