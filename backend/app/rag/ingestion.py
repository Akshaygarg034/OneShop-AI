from uuid import uuid4
import json
import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams


# DATA_FILE = "data/products_vector.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = f"{BASE_DIR}/data/products_vector.json"
print(f"BASE_DIR: {BASE_DIR}")
COLLECTION_NAME = "product_embeddings"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

print("Loading products...")

with open(DATA_FILE, "r") as file:
    products = json.load(file)

print(f"Loaded {len(products)} products")

documents = []
for product in products:

    content = f"""
    Product Description:
    {product.get('description', '')}
    Features:
    {', '.join(product.get('features', []))}
    """

    documents.append( 
        Document(
            page_content=content,
            metadata={
                "product_id": product["id"],
                "name": product["name"],
                "brand": product["brand"],
                "type": product["type"],
                "category": product["category"]
            }
        )
    )

print(f"Created {len(documents)} product documents")

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
client = QdrantClient(url="http://localhost:6333")

if client.collection_exists(COLLECTION_NAME):
    client.delete_collection(COLLECTION_NAME)


client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(
        size=384,
        distance=Distance.COSINE,
    ),
)

vector_store = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
)

ids = [str(uuid4()) for _ in documents]
vector_store.add_documents(documents=documents, ids=ids)

print("Product indexing completed successfully")
print(f"Total vectors stored: {client.count(COLLECTION_NAME).count}")


if __name__ == "__main__":

    results = vector_store.similarity_search(
        query="best mobile with AI camera",
        k=3
    )

    print("\nSearch Results\n")

    for index, doc in enumerate(results, start=1):
        print(f"\nResult {index}")
        print("Content:")
        print(doc.page_content)
        print("Metadata:")
        print(doc.metadata)
