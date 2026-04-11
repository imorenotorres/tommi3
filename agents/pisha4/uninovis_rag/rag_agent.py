#!/usr/bin/env python3
"""
UNINOVIS RAG Agent - AI & Responsibility Research
Retrieval-Augmented Generation agent for querying UNINOVIS alliance research.
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv

load_dotenv()


class UNINOVISRagAgent:
    """RAG agent for UNINOVIS AI & Responsibility research."""

    def __init__(
        self,
        data_dir: str = "data",
        embedding_model: str = "all-MiniLM-L6-v2",
        llm_provider: str = "ollama",
        llm_model: str = "mistral"
    ):
        self.data_dir = Path(data_dir)
        self.metadata_dir = self.data_dir / "metadata"
        self.papers_dir = self.data_dir / "papers"
        self.vectorstore_dir = self.data_dir / "vectorstore"

        self.embedding_model_name = embedding_model
        self.llm_provider = llm_provider
        self.llm_model = llm_model

        self.papers_metadata: List[Dict] = []
        self.vectorstore = None
        self.embeddings = None
        self.llm = None

        self._load_metadata()

    def _load_metadata(self):
        """Load paper metadata from JSON files."""
        full_collection_path = self.metadata_dir / "full_collection.json"

        if full_collection_path.exists():
            with open(full_collection_path, encoding="utf-8") as f:
                data = json.load(f)

            for uni_data in data.get("universities", {}).values():
                self.papers_metadata.extend(uni_data.get("papers", []))

            print(f"Loaded metadata for {len(self.papers_metadata)} papers")
        else:
            print("No metadata found. Run openalex_collector.py first.")

    def initialize_embeddings(self):
        """Initialize the embedding model."""
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model_name
            )
            print(f"Initialized embeddings: {self.embedding_model_name}")
        except ImportError:
            print("Install sentence-transformers: pip install sentence-transformers")
            raise

    def initialize_llm(self):
        """Initialize the LLM based on provider."""
        if self.llm_provider == "ollama":
            try:
                from langchain_community.llms import Ollama
                self.llm = Ollama(model=self.llm_model)
                print(f"Initialized Ollama LLM: {self.llm_model}")
            except ImportError:
                print("Install ollama: pip install ollama")
                raise

        elif self.llm_provider == "mistral":
            try:
                from langchain_community.llms import MistralAI
                self.llm = MistralAI(
                    model=self.llm_model,
                    mistral_api_key=os.getenv("MISTRAL_API_KEY")
                )
                print(f"Initialized Mistral LLM: {self.llm_model}")
            except ImportError:
                print("Install mistralai: pip install mistralai")
                raise

        elif self.llm_provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
                self.llm = ChatOpenAI(
                    model=self.llm_model,
                    openai_api_key=os.getenv("OPENAI_API_KEY")
                )
                print(f"Initialized OpenAI LLM: {self.llm_model}")
            except ImportError:
                print("Install openai: pip install openai")
                raise

    def build_vectorstore(self, force_rebuild: bool = False):
        """Build or load the vector store from paper metadata and PDFs."""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_community.vectorstores import Chroma
        from langchain.schema import Document

        self.vectorstore_dir.mkdir(parents=True, exist_ok=True)

        # Check if vectorstore exists
        if not force_rebuild and (self.vectorstore_dir / "chroma.sqlite3").exists():
            print("Loading existing vectorstore...")
            self.vectorstore = Chroma(
                persist_directory=str(self.vectorstore_dir),
                embedding_function=self.embeddings
            )
            print(f"Loaded vectorstore with {self.vectorstore._collection.count()} documents")
            return

        print("Building vectorstore from paper metadata...")

        # Create documents from metadata
        documents = []
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        for paper in self.papers_metadata:
            # Create document from metadata
            content_parts = []

            if paper.get("title"):
                content_parts.append(f"Title: {paper['title']}")

            if paper.get("abstract"):
                content_parts.append(f"Abstract: {paper['abstract']}")

            if paper.get("concepts"):
                concepts = ", ".join([c["name"] for c in paper["concepts"][:5] if c.get("name")])
                if concepts:
                    content_parts.append(f"Topics: {concepts}")

            if paper.get("authors"):
                authors = ", ".join([a["name"] for a in paper["authors"][:5] if a.get("name")])
                if authors:
                    content_parts.append(f"Authors: {authors}")

            if not content_parts:
                continue

            content = "\n".join(content_parts)

            # Create metadata for the document
            doc_metadata = {
                "paper_id": paper.get("id", ""),
                "title": paper.get("title", ""),
                "doi": paper.get("doi", ""),
                "publication_year": paper.get("publication_year", ""),
                "cited_by_count": paper.get("cited_by_count", 0),
                "affiliations": ", ".join(paper.get("affiliations", [])[:3]),
                "source": paper.get("source", ""),
                "is_open_access": paper.get("is_open_access", False)
            }

            # Split long documents
            splits = text_splitter.split_text(content)
            for i, split in enumerate(splits):
                doc = Document(
                    page_content=split,
                    metadata={**doc_metadata, "chunk": i}
                )
                documents.append(doc)

        print(f"Created {len(documents)} document chunks")

        # Try to load PDFs if available
        pdf_documents = self._load_pdfs()
        documents.extend(pdf_documents)

        # Create vectorstore
        self.vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=str(self.vectorstore_dir)
        )

        print(f"Built vectorstore with {len(documents)} total chunks")

    def _load_pdfs(self) -> List:
        """Load and process PDF files."""
        from langchain.schema import Document
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        documents = []
        pdf_files = list(self.papers_dir.glob("*.pdf"))

        if not pdf_files:
            print("No PDF files found")
            return documents

        print(f"Processing {len(pdf_files)} PDF files...")

        try:
            from pypdf import PdfReader
        except ImportError:
            print("pypdf not installed, skipping PDF processing")
            return documents

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        for pdf_path in pdf_files:
            try:
                reader = PdfReader(pdf_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""

                if len(text) < 100:  # Skip nearly empty PDFs
                    continue

                # Find matching metadata
                paper_id = pdf_path.stem.replace("_", "/")
                paper_meta = next(
                    (p for p in self.papers_metadata if p.get("id") == paper_id),
                    {}
                )

                doc_metadata = {
                    "paper_id": paper_id,
                    "title": paper_meta.get("title", pdf_path.stem),
                    "source_type": "pdf",
                    "doi": paper_meta.get("doi", "")
                }

                splits = text_splitter.split_text(text)
                for i, split in enumerate(splits):
                    doc = Document(
                        page_content=split,
                        metadata={**doc_metadata, "chunk": i, "total_chunks": len(splits)}
                    )
                    documents.append(doc)

                print(f"  Processed: {pdf_path.name} ({len(splits)} chunks)")

            except Exception as e:
                print(f"  Error processing {pdf_path.name}: {e}")

        return documents

    def query(self, question: str, k: int = 5) -> Dict[str, Any]:
        """Query the RAG system."""
        if not self.vectorstore:
            raise ValueError("Vectorstore not initialized. Call build_vectorstore() first.")

        if not self.llm:
            raise ValueError("LLM not initialized. Call initialize_llm() first.")

        # Retrieve relevant documents
        docs = self.vectorstore.similarity_search(question, k=k)

        # Build context from retrieved documents
        context_parts = []
        sources = []

        for doc in docs:
            context_parts.append(doc.page_content)
            sources.append({
                "title": doc.metadata.get("title", "Unknown"),
                "doi": doc.metadata.get("doi", ""),
                "year": doc.metadata.get("publication_year", ""),
                "affiliations": doc.metadata.get("affiliations", "")
            })

        context = "\n\n---\n\n".join(context_parts)

        # Create prompt
        prompt = f"""You are an expert research assistant helping to analyze the scientific production
of the UNINOVIS alliance universities on AI and Responsibility topics.

Based on the following research excerpts, answer the question. Be specific and cite sources when possible.
If the information is not available in the context, say so.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""

        # Generate response
        response = self.llm.invoke(prompt)

        return {
            "answer": response if isinstance(response, str) else response.content,
            "sources": sources,
            "num_sources": len(sources)
        }

    def get_university_summary(self, university_acronym: str) -> Dict[str, Any]:
        """Get a summary of research from a specific university."""
        uni_papers = [
            p for p in self.papers_metadata
            if university_acronym.upper() in str(p.get("affiliations", [])).upper()
        ]

        if not uni_papers:
            return {"error": f"No papers found for {university_acronym}"}

        # Get top topics
        all_concepts = []
        for paper in uni_papers:
            all_concepts.extend([c["name"] for c in paper.get("concepts", []) if c.get("name")])

        from collections import Counter
        top_topics = Counter(all_concepts).most_common(10)

        return {
            "university": university_acronym,
            "total_papers": len(uni_papers),
            "top_topics": top_topics,
            "total_citations": sum(p.get("cited_by_count", 0) for p in uni_papers),
            "open_access_papers": sum(1 for p in uni_papers if p.get("is_open_access"))
        }

    def find_collaboration_opportunities(self, topic: str) -> List[Dict]:
        """Find universities working on similar topics for potential collaboration."""
        if not self.vectorstore:
            raise ValueError("Vectorstore not initialized")

        docs = self.vectorstore.similarity_search(topic, k=20)

        # Group by affiliation
        from collections import defaultdict
        uni_papers = defaultdict(list)

        for doc in docs:
            affiliations = doc.metadata.get("affiliations", "")
            for aff in affiliations.split(", "):
                if aff:
                    uni_papers[aff].append({
                        "title": doc.metadata.get("title"),
                        "year": doc.metadata.get("publication_year")
                    })

        return [
            {"university": uni, "papers": papers, "count": len(papers)}
            for uni, papers in sorted(uni_papers.items(), key=lambda x: -len(x[1]))
        ]


def main():
    """Demo the RAG agent."""
    import argparse

    parser = argparse.ArgumentParser(description="UNINOVIS RAG Agent")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild vectorstore")
    parser.add_argument("--llm", default="ollama", choices=["ollama", "mistral", "openai"])
    parser.add_argument("--model", default="mistral", help="LLM model name")
    parser.add_argument("--query", "-q", help="Query to run")

    args = parser.parse_args()

    agent = UNINOVISRagAgent(
        data_dir=args.data_dir,
        llm_provider=args.llm,
        llm_model=args.model
    )

    print("\nInitializing agent...")
    agent.initialize_embeddings()
    agent.initialize_llm()
    agent.build_vectorstore(force_rebuild=args.rebuild)

    if args.query:
        print(f"\nQuery: {args.query}")
        result = agent.query(args.query)
        print(f"\nAnswer: {result['answer']}")
        print(f"\nSources ({result['num_sources']}):")
        for src in result['sources']:
            print(f"  - {src['title']} ({src['year']})")
    else:
        # Interactive mode
        print("\n" + "=" * 60)
        print("UNINOVIS RAG Agent - Interactive Mode")
        print("Type 'quit' to exit, 'summary <UNI>' for university summary")
        print("=" * 60)

        while True:
            try:
                user_input = input("\nYour question: ").strip()

                if not user_input:
                    continue

                if user_input.lower() == "quit":
                    break

                if user_input.lower().startswith("summary "):
                    uni = user_input.split(" ", 1)[1].upper()
                    summary = agent.get_university_summary(uni)
                    print(json.dumps(summary, indent=2))
                    continue

                result = agent.query(user_input)
                print(f"\n{result['answer']}")
                print(f"\n[Sources: {result['num_sources']} documents]")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    main()
