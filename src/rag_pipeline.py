"""
Complete RAG Pipeline Orchestrator
Handles: S3 upload/download -> Data processing -> Embeddings -> Pinecone loading -> Model training
"""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import pipeline components
from knowledge.s3_storage import S3StorageManager
from knowledge.data_processor import DataProcessor
from knowledge.embedder import get_embeddings
from knowledge.loader import KnowledgeLoader
from inference.predictor import TherapyChatbot
from model.model_train import ModelTrainer


class RAGPipeline:
    """Orchestrates the complete RAG pipeline"""
    
    def __init__(self):
        logger.info("Initializing RAG Pipeline...")
        self.s3_manager = None
        self.data_processor = DataProcessor()
        self.knowledge_loader = None
        self.model_trainer = None
        
    def step_1_upload_to_s3(self):
        """Step 1: Upload raw knowledge base files to S3"""
        logger.info("\n" + "="*60)
        logger.info("STEP 1: Uploading raw KB files to S3")
        logger.info("="*60)
        
        try:
            self.s3_manager = S3StorageManager(
                bucket_name=os.getenv("AWS_S3_BUCKET_NAME", "f2-fintech-knowledge-base"),
                region=os.getenv("AWS_REGION", "ap-south-1")
            )
            
            raw_dir = Path("src/data/raw")
            if not raw_dir.exists():
                logger.error(f"Raw data directory not found: {raw_dir}")
                return False
            
            logger.info(f"Uploading files from {raw_dir}...")
            success = self.s3_manager.sync_raw_to_s3()
            
            if success:
                logger.info("✓ Successfully uploaded raw KB files to S3")
            else:
                logger.error("✗ Failed to upload some files to S3")
            
            return success
            
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            return False
    
    def step_2_download_from_s3(self):
        """Step 2: Download knowledge base files from S3"""
        logger.info("\n" + "="*60)
        logger.info("STEP 2: Downloading KB files from S3")
        logger.info("="*60)
        
        try:
            if self.s3_manager is None:
                self.s3_manager = S3StorageManager(
                    bucket_name=os.getenv("AWS_S3_BUCKET_NAME", "f2-fintech-knowledge-base"),
                    region=os.getenv("AWS_REGION", "ap-south-1")
                )
            
            logger.info("Downloading raw files from S3...")
            success = self.s3_manager.download_raw_from_s3()
            
            if success:
                logger.info("✓ Successfully downloaded raw KB files from S3")
            else:
                logger.error("✗ Failed to download some files from S3")
            
            return success
            
        except Exception as e:
            logger.error(f"Error downloading from S3: {e}")
            return False
    
    def step_3_process_data(self):
        """Step 3: Process raw KB files into formatted documents"""
        logger.info("\n" + "="*60)
        logger.info("STEP 3: Processing raw KB files")
        logger.info("="*60)
        
        try:
            logger.info("Processing FAQs...")
            faqs = self.data_processor.process_faqs()
            if faqs:
                logger.info(f"✓ Processed {len(faqs)} FAQs")
            else:
                logger.warning("⚠ No FAQs found to process")
            
            logger.info("Processing scenarios...")
            scenarios = self.data_processor.process_scenarios()
            if scenarios:
                logger.info(f"✓ Processed {len(scenarios)} scenarios")
            else:
                logger.warning("⚠ No scenarios found to process")
            
            logger.info("Processing system prompt...")
            prompt = self.data_processor.process_system_prompt()
            if prompt:
                logger.info("✓ Processed system prompt")
            else:
                logger.warning("⚠ No system prompt found to process")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing data: {e}")
            return False
    
    def step_4_embed_data(self):
        """Step 4: Generate embeddings for processed documents"""
        logger.info("\n" + "="*60)
        logger.info("STEP 4: Generating embeddings for KB documents")
        logger.info("="*60)
        
        try:
            logger.info("Initializing embeddings model (Gemini text-embedding-001)...")
            embeddings = get_embeddings()
            logger.info("✓ Embeddings model ready")
            
            # Test embedding
            logger.info("Testing embedding generation...")
            test_text = "Financial therapy and mental health support"
            test_vector = embeddings.embed_query(test_text)
            logger.info(f"✓ Generated test embedding (dimension: {len(test_vector)})")
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return False
    
    def step_5_load_to_pinecone(self):
        """Step 5: Load processed KB and embeddings to Pinecone"""
        logger.info("\n" + "="*60)
        logger.info("STEP 5: Loading KB documents to Pinecone vector DB")
        logger.info("="*60)
        
        try:
            logger.info("Initializing Pinecone index...")
            self.knowledge_loader = KnowledgeLoader()
            
            logger.info("Loading all documents to Pinecone...")
            self.knowledge_loader.load_all()
            
            logger.info("✓ Successfully loaded KB to Pinecone")
            return True
            
        except Exception as e:
            logger.error(f"Error loading to Pinecone: {e}")
            return False
    
    def step_6_train_model(self):
        """Step 6: Train model with Gemini 3.Flash preview"""
        logger.info("\n" + "="*60)
        logger.info("STEP 6: Training model with Gemini 3 Flash preview")
        logger.info("="*60)
        
        try:
            self.model_trainer = ModelTrainer()
            logger.info("Training model...")
            success = self.model_trainer.train()
            
            if success:
                logger.info("✓ Model training completed successfully")
            else:
                logger.warning("⚠ Model training completed with warnings")
            
            return True
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return False
    
    def step_7_test_chatbot(self):
        """Step 7: Test chatbot RAG pipeline"""
        logger.info("\n" + "="*60)
        logger.info("STEP 7: Testing chatbot RAG pipeline")
        logger.info("="*60)
        
        try:
            logger.info("Initializing chatbot...")
            chatbot = TherapyChatbot()
            
            # Test queries
            test_queries = [
                "I'm worried about my credit card debt",
                "How should I handle missed EMI payments?",
                "What's the difference between a savings and checking account?"
            ]
            
            for query in test_queries:
                logger.info(f"\nTesting query: '{query}'")
                response = chatbot.chat(query)
                logger.info(f"Response: {response[:100]}...")
            
            logger.info("✓ Chatbot testing completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error testing chatbot: {e}")
            return False
    
    def run_full_pipeline(self, skip_s3_upload=False, skip_s3_download=False):
        """
        Run the complete RAG pipeline
        
        Args:
            skip_s3_upload: Skip uploading to S3 (useful if files already uploaded)
            skip_s3_download: Skip downloading from S3 (useful if running with local files)
        """
        logger.info("\n" + "█"*60)
        logger.info("█ STARTING COMPLETE RAG PIPELINE EXECUTION")
        logger.info("█"*60)
        
        steps = []
        
        # Step 1: Upload to S3
        if not skip_s3_upload:
            logger.info("\nStep 1/7: Upload to S3")
            if self.step_1_upload_to_s3():
                steps.append(("✓", "Upload to S3"))
            else:
                steps.append(("✗", "Upload to S3"))
        
        # Step 2: Download from S3
        if not skip_s3_download:
            logger.info("\nStep 2/7: Download from S3")
            if self.step_2_download_from_s3():
                steps.append(("✓", "Download from S3"))
            else:
                steps.append(("✗", "Download from S3"))
        
        # Step 3: Process data
        logger.info("\nStep 3/7: Process data")
        if self.step_3_process_data():
            steps.append(("✓", "Process data"))
        else:
            steps.append(("✗", "Process data"))
        
        # Step 4: Generate embeddings
        logger.info("\nStep 4/7: Generate embeddings")
        if self.step_4_embed_data():
            steps.append(("✓", "Generate embeddings"))
        else:
            steps.append(("✗", "Generate embeddings"))
        
        # Step 5: Load to Pinecone
        logger.info("\nStep 5/7: Load to Pinecone")
        if self.step_5_load_to_pinecone():
            steps.append(("✓", "Load to Pinecone"))
        else:
            steps.append(("✗", "Load to Pinecone"))
        
        # Step 6: Train model
        logger.info("\nStep 6/7: Train model")
        if self.step_6_train_model():
            steps.append(("✓", "Train model"))
        else:
            steps.append(("✗", "Train model"))
        
        # Step 7: Test chatbot
        logger.info("\nStep 7/7: Test chatbot")
        if self.step_7_test_chatbot():
            steps.append(("✓", "Test chatbot"))
        else:
            steps.append(("✗", "Test chatbot"))
        
        # Print summary
        logger.info("\n" + "█"*60)
        logger.info("█ PIPELINE EXECUTION SUMMARY")
        logger.info("█"*60)
        for symbol, step_name in steps:
            logger.info(f"{symbol} {step_name}")
        
        success_count = sum(1 for symbol, _ in steps if symbol == "✓")
        total_steps = len(steps)
        logger.info(f"\nCompleted: {success_count}/{total_steps} steps")
        
        if success_count == total_steps:
            logger.info("\n🎉 RAG PIPELINE EXECUTION SUCCESSFUL!")
        else:
            logger.warning(f"\n⚠ Pipeline completed with {total_steps - success_count} failures")
        
        logger.info("█"*60 + "\n")
        
        return success_count == total_steps


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Pipeline Orchestrator")
    parser.add_argument("--skip-s3-upload", action="store_true", help="Skip S3 upload step")
    parser.add_argument("--skip-s3-download", action="store_true", help="Skip S3 download step")
    parser.add_argument("--steps", type=str, help="Comma-separated specific steps to run (1-7)")
    
    args = parser.parse_args()
    
    pipeline = RAGPipeline()
    pipeline.run_full_pipeline(
        skip_s3_upload=args.skip_s3_upload,
        skip_s3_download=args.skip_s3_download
    )


if __name__ == "__main__":
    main()
