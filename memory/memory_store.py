"""MemoryStore class for Qdrant vector database operations."""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from datetime import datetime
from typing import List, Dict, Optional
import os

from memory.embeddings import embed


class MemoryStore:
    """Manages long-term memory storage and retrieval using Qdrant."""
    
    COLLECTION_NAME = "agent_memory"
    VECTOR_SIZE = 384  # all-MiniLM-L6-v2 produces 384-dimensional embeddings
    DISTANCE = Distance.COSINE
    
    def __init__(self, qdrant_url: Optional[str] = None):
        """
        Initialize MemoryStore.
        
        Args:
            qdrant_url: Qdrant server URL (default: http://localhost:6333)
        """
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.client = QdrantClient(url=self.qdrant_url)
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.COLLECTION_NAME not in collection_names:
                # Create collection
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=self.DISTANCE
                    )
                )
                print(f"[OK] Created Qdrant collection: {self.COLLECTION_NAME}")
            else:
                # Check if collection has correct vector size, recreate if needed
                collection_info = self.client.get_collection(self.COLLECTION_NAME)
                if collection_info.config.params.vectors.size != self.VECTOR_SIZE:
                    print(f"[WARNING] Collection exists with wrong vector size. Deleting and recreating...")
                    self.client.delete_collection(self.COLLECTION_NAME)
                    self.client.create_collection(
                        collection_name=self.COLLECTION_NAME,
                        vectors_config=VectorParams(
                            size=self.VECTOR_SIZE,
                            distance=self.DISTANCE
                        )
                    )
                    print(f"[OK] Recreated Qdrant collection: {self.COLLECTION_NAME}")
                else:
                    print(f"[OK] Qdrant collection {self.COLLECTION_NAME} already exists")
        except Exception as e:
            print(f"[WARNING] Could not connect to Qdrant: {e}")
            print("  Memory features will be unavailable until Qdrant is started.")
            print("  To start Qdrant: docker-compose up -d")
    
    def store_memory(self, user_email: str, fact_text: str, importance: int):
        """
        Store a memory in Qdrant.
        
        Args:
            user_email: User's email address
            fact_text: The factual memory text to store
            importance: Importance score (1-5)
        """
        try:
            # Generate embedding for fact_text only
            vector = embed(fact_text)
            print(f"[MEMORY] Generated embedding of size {len(vector)} for: {fact_text[:50]}...")
            
            # Create payload (DO NOT include email or timestamp in vector)
            payload = {
                "user_email": user_email,
                "fact_text": fact_text,
                "importance": importance,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Generate unique ID (using timestamp + hash of fact_text)
            import hashlib
            point_id = int(hashlib.md5(f"{user_email}{fact_text}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:15], 16)
            
            # Store in Qdrant
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            
            # Verify the vector was stored
            try:
                stored_point = self.client.retrieve(
                    collection_name=self.COLLECTION_NAME,
                    ids=[point_id]
                )
                if stored_point and len(stored_point) > 0:
                    stored_vector = stored_point[0].vector
                    if stored_vector:
                        print(f"[OK] Stored memory for {user_email}: {fact_text[:50]}... (vector size: {len(stored_vector)})")
                    else:
                        print(f"[WARNING] Memory stored but vector is None!")
                else:
                    print(f"[WARNING] Could not verify stored memory")
            except Exception as verify_error:
                print(f"[WARNING] Could not verify stored memory: {verify_error}")
            
            print(f"[OK] Stored memory for {user_email}: {fact_text[:50]}...")
        except Exception as e:
            print(f"[ERROR] Error storing memory: {e}")
    
    def search_memory(self, user_email: str, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search memories for a user.
        
        Args:
            user_email: User's email address
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            List of memory dictionaries with payload and score
        """
        try:
            # Generate embedding for query
            query_vector = embed(query)
            
            # Qdrant client doesn't have search() method, use scroll + manual similarity
            import numpy as np
            
            # Scroll to get all points with user_email filter
            # IMPORTANT: with_vectors=True to get the vectors
            scroll_result = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="user_email",
                            match=MatchValue(value=user_email)
                        )
                    ]
                ),
                limit=1000,  # Get all user's memories
                with_vectors=True  # CRITICAL: Include vectors in the response
            )
            
            points = scroll_result[0]  # scroll_result is (points, next_page_offset)
            print(f"[MEMORY] Found {len(points)} total memories for user {user_email}")
            
            if len(points) == 0:
                print(f"[MEMORY] No memories stored for user {user_email}")
                return []
            
            # Debug: Check if points have vectors
            points_with_vectors = [p for p in points if p.vector is not None and len(p.vector) > 0]
            print(f"[MEMORY] Points with vectors: {len(points_with_vectors)} out of {len(points)}")
            
            if len(points_with_vectors) == 0:
                print(f"[MEMORY] WARNING: No points have vectors! This might mean vectors weren't requested in scroll.")
                print(f"[MEMORY] Falling back to importance-based retrieval (no similarity scoring)")
                # Return memories anyway based on importance only
                return [{
                    "fact_text": p.payload.get("fact_text", ""),
                    "importance": p.payload.get("importance", 1),
                    "similarity": 0.5,  # Default similarity when no vector
                    "created_at": p.payload.get("created_at", "")
                } for p in sorted(points, key=lambda p: p.payload.get("importance", 1), reverse=True)[:top_k]]
            
            # Calculate similarity scores manually
            query_vec = np.array(query_vector, dtype=np.float32)
            memories_with_scores = []
            
            for point in points_with_vectors:
                if point.vector:
                    point_vec = np.array(point.vector, dtype=np.float32)
                    # Cosine similarity
                    dot_product = np.dot(query_vec, point_vec)
                    norm_query = np.linalg.norm(query_vec)
                    norm_point = np.linalg.norm(point_vec)
                    if norm_query > 0 and norm_point > 0:
                        similarity = dot_product / (norm_query * norm_point)
                        memories_with_scores.append({
                            "fact_text": point.payload.get("fact_text", ""),
                            "importance": point.payload.get("importance", 1),
                            "similarity": float(similarity),
                            "created_at": point.payload.get("created_at", "")
                        })
            
            print(f"[MEMORY] Calculated similarity for {len(memories_with_scores)} memories")
            if memories_with_scores:
                print(f"[MEMORY] Similarity scores range: {min(m['similarity'] for m in memories_with_scores):.3f} to {max(m['similarity'] for m in memories_with_scores):.3f}")
            
            # Sort by similarity and return top_k
            memories_with_scores.sort(key=lambda x: x["similarity"], reverse=True)
            return memories_with_scores[:top_k]
        except Exception as e:
            print(f"[ERROR] Error searching memory: {e}")
            return []
    
    def get_relevant_memory(self, user_email: str, query: str, top_k: int = 5) -> List[str]:
        """
        Get relevant memories with scoring.
        
        Scoring formula: final_score = similarity * 0.7 + importance * 0.3
        
        Args:
            user_email: User's email address
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            Sorted list of fact_text values (by final_score)
        """
        memories = self.search_memory(user_email, query, top_k=top_k * 2)  # Get more for filtering
        
        # Apply scoring
        scored_memories = []
        for mem in memories:
            similarity = mem.get("similarity", 0.0)
            importance = mem.get("importance", 1)
            
            # Normalize importance to 0-1 scale (1-5 -> 0-1)
            normalized_importance = (importance - 1) / 4.0
            
            # Calculate final score
            final_score = (similarity * 0.7) + (normalized_importance * 0.3)
            
            scored_memories.append({
                "fact_text": mem["fact_text"],
                "final_score": final_score,
                "similarity": similarity,
                "importance": importance
            })
        
        # Sort by final_score (descending)
        scored_memories.sort(key=lambda x: x["final_score"], reverse=True)
        
        # Lower threshold - include memories even if similarity is low but importance is high
        # Or if final_score > 0.2 (more lenient)
        filtered_memories = [m for m in scored_memories if m["final_score"] > 0.2 or m["importance"] >= 4]
        
        # Return top_k fact_text values
        result = [mem["fact_text"] for mem in filtered_memories[:top_k]]
        if result:
            print(f"[MEMORY] Found {len(result)} relevant memories with scores:")
            for i, mem in enumerate(filtered_memories[:top_k], 1):
                print(f"  {i}. Score: {mem['final_score']:.3f} (sim: {mem['similarity']:.3f}, imp: {mem['importance']}) - {mem['fact_text'][:60]}...")
        else:
            print(f"[MEMORY] No relevant memories found for query: '{query[:50]}...'")
            if scored_memories:
                print(f"[MEMORY] All memories filtered out. Top memory had score: {scored_memories[0]['final_score']:.3f}")
        return result
    
    def find_similar_memories(self, user_email: str, fact_text: str, similarity_threshold: float = 0.7) -> List[Dict]:
        """
        Find memories that are similar to the given fact_text.
        Used to detect conflicts or updates.
        
        Args:
            user_email: User's email address
            fact_text: The fact text to search for similar memories
            similarity_threshold: Minimum similarity to consider (0-1)
            
        Returns:
            List of similar memories with their IDs and similarity scores
        """
        try:
            query_vector = embed(fact_text)
            import numpy as np
            
            # Get all user's memories
            scroll_result = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="user_email",
                            match=MatchValue(value=user_email)
                        )
                    ]
                ),
                limit=1000,
                with_vectors=True
            )
            
            points = scroll_result[0]
            similar_memories = []
            query_vec = np.array(query_vector, dtype=np.float32)
            
            for point in points:
                if point.vector:
                    point_vec = np.array(point.vector, dtype=np.float32)
                    dot_product = np.dot(query_vec, point_vec)
                    norm_query = np.linalg.norm(query_vec)
                    norm_point = np.linalg.norm(point_vec)
                    if norm_query > 0 and norm_point > 0:
                        similarity = dot_product / (norm_query * norm_point)
                        if similarity >= similarity_threshold:
                            similar_memories.append({
                                "id": point.id,
                                "fact_text": point.payload.get("fact_text", ""),
                                "similarity": float(similarity),
                                "importance": point.payload.get("importance", 1),
                                "created_at": point.payload.get("created_at", "")
                            })
            
            # Sort by similarity (descending)
            similar_memories.sort(key=lambda x: x["similarity"], reverse=True)
            return similar_memories
        except Exception as e:
            print(f"[ERROR] Error finding similar memories: {e}")
            return []
    
    def delete_memory(self, user_email: str, memory_id: int) -> bool:
        """
        Delete a specific memory by ID.
        
        Args:
            user_email: User's email (for verification)
            memory_id: ID of the memory point to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Verify the memory belongs to the user
            point = self.client.retrieve(
                collection_name=self.COLLECTION_NAME,
                ids=[memory_id]
            )
            
            if not point or len(point) == 0:
                print(f"[WARNING] Memory with ID {memory_id} not found")
                return False
            
            if point[0].payload.get("user_email") != user_email:
                print(f"[WARNING] Memory {memory_id} does not belong to user {user_email}")
                return False
            
            # Delete the memory
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=[memory_id]
            )
            print(f"[OK] Deleted memory {memory_id} for user {user_email}")
            return True
        except Exception as e:
            print(f"[ERROR] Error deleting memory: {e}")
            return False
    
    def update_memory(self, user_email: str, old_fact_text: str, new_fact_text: str, new_importance: int = None) -> bool:
        """
        Update an existing memory by finding and replacing it.
        
        Args:
            user_email: User's email address
            old_fact_text: The old fact text to find and replace
            new_fact_text: The new fact text
            new_importance: Optional new importance score (if None, keeps old importance)
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Find similar memories
            similar = self.find_similar_memories(user_email, old_fact_text, similarity_threshold=0.7)
            
            if not similar:
                print(f"[WARNING] No similar memory found to update for: {old_fact_text[:50]}...")
                return False
            
            # Use the most similar memory
            memory_to_update = similar[0]
            memory_id = memory_to_update["id"]
            
            # Get the old memory to preserve importance if not specified
            old_point = self.client.retrieve(
                collection_name=self.COLLECTION_NAME,
                ids=[memory_id]
            )
            
            if not old_point or len(old_point) == 0:
                return False
            
            old_importance = new_importance if new_importance is not None else old_point[0].payload.get("importance", 3)
            
            # Generate new embedding
            new_vector = embed(new_fact_text)
            
            # Update the memory
            self.client.set_payload(
                collection_name=self.COLLECTION_NAME,
                payload={
                    "fact_text": new_fact_text,
                    "importance": old_importance,
                    "updated_at": datetime.utcnow().isoformat()
                },
                points=[memory_id]
            )
            
            # Update the vector
            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=new_vector,
                        payload={
                            "user_email": user_email,
                            "fact_text": new_fact_text,
                            "importance": old_importance,
                            "created_at": old_point[0].payload.get("created_at", datetime.utcnow().isoformat()),
                            "updated_at": datetime.utcnow().isoformat()
                        }
                    )
                ]
            )
            
            print(f"[OK] Updated memory {memory_id}: '{old_fact_text[:50]}...' -> '{new_fact_text[:50]}...'")
            return True
        except Exception as e:
            print(f"[ERROR] Error updating memory: {e}")
            return False

