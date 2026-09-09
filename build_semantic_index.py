"""Build the filtered Gemini semantic-search index from local official PDFs."""

from pathlib import Path
import argparse
import json
import os

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from app.semantic_search import (
    DEFAULT_CORPUS_PATH,
    build_semantic_corpus,
    create_client,
    embed_documents,
    save_semantic_index,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-only", action="store_true")
    parser.add_argument("--embed-existing", action="store_true")
    args = parser.parse_args()

    corpus = (
        json.loads(DEFAULT_CORPUS_PATH.read_text(encoding="utf-8"))
        if args.embed_existing
        else build_semantic_corpus()
    )
    print(
        f"Extracted {len(corpus):,} chunks across "
        f"{len({row['ticker'] for row in corpus})} banks and "
        f"{len({(row['ticker'], row['period']) for row in corpus})} documents."
    )
    if args.corpus_only:
        DEFAULT_CORPUS_PATH.write_text(
            json.dumps(corpus, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return

    client = create_client(os.getenv("GEMINI_API_KEY", ""))
    embeddings = embed_documents(client, corpus)
    metadata = save_semantic_index(corpus, embeddings)
    print(
        f"Wrote semantic index: {metadata['chunk_count']:,} chunks, "
        f"{metadata['embedding_dimension']} dimensions."
    )


if __name__ == "__main__":
    main()
