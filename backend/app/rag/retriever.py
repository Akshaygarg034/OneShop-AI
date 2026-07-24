from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


COLLECTION_NAME = "product_embeddings"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

client = QdrantClient(url="http://localhost:6333")

vector_store = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
)


retriever = vector_store.as_retriever(
    search_kwargs={"k": 3}
)


print("Product Search Ready")
print("Type 'exit' to quit\n")


while True:

    query = input("Search: ").strip()
    if query.lower() == "exit":
        break

    products = retriever.invoke(query)
    print("\nRecommended Products")
    print("-" * 50)

    for index, product in enumerate(products, start=1):

        print(f"\nResult {index}")

        print("Product Details:")
        print(product.metadata)

        print("\nProduct Description:")
        print(product.page_content)

    print("-" * 50)