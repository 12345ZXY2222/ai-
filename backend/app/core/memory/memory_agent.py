import os
import datetime
from app.core.memory.associative_memory import AssociativeMemory
from app.core.memory.scratch import Scratch
from app.core.memory.utils import get_embedding

class MemoryAgent:
    def __init__(self, agent_id, base_path="/home/peirm/ai模拟平台/backend/data/memory"):
        self.agent_id = agent_id
        self.agent_path = os.path.join(base_path, agent_id)
        
        if not os.path.exists(self.agent_path):
            os.makedirs(self.agent_path, exist_ok=True)
            
        self.memory = AssociativeMemory(self.agent_path)
        self.scratch = Scratch(os.path.join(self.agent_path, "scratch.json"))
        
        # Initialize scratch name if empty
        if not self.scratch.name:
            self.scratch.name = agent_id

    def save(self):
        self.memory.save(self.agent_path)
        self.scratch.save(os.path.join(self.agent_path, "scratch.json"))

    def add_observation(self, content, importance=1):
        """
        Inject a memory/observation into the agent's associative memory.
        """
        created = datetime.datetime.now()
        expiration = None
        
        # Simple keyword extraction (naive)
        keywords = set(content.split()[:5]) 
        
        # Get embedding
        embedding = get_embedding(content)
        embedding_pair = (content, embedding)
        
        # Add to memory stream
        self.memory.add_event(created, expiration, self.agent_id, "observed", content, 
                              content, keywords, importance, embedding_pair, None)
        
        # Also update scratch if needed (e.g. current action context)
        # For now, we just save to long-term memory
        self.save()
        return f"Memory added: {content}"

    def retrieve(self, query, count=5):
        """
        Retrieve relevant memories based on query embedding.
        """
        query_embedding = get_embedding(query)
        
        # Simple cosine similarity search over all nodes
        # In a real production system, use a Vector DB (FAISS, Chroma, etc.)
        # Here we iterate over self.memory.id_to_node
        
        scores = []
        for node_id, node in self.memory.id_to_node.items():
            if node.embedding_key in self.memory.embeddings:
                emb = self.memory.embeddings[node.embedding_key]
                # Calculate cosine similarity
                from app.core.memory.utils import cos_sim
                similarity = cos_sim(query_embedding, emb)
                
                # Weighting Logic:
                # node.poignancy is 1-10. Default 5.
                # We want high importance to boost the score.
                # Formula: score = similarity * (1 + (poignancy - 5) * 0.1)
                # If poignancy=10 -> multiplier 1.5
                # If poignancy=1 -> multiplier 0.6
                # If poignancy=5 -> multiplier 1.0
                
                importance_multiplier = 1 + (node.poignancy - 5) * 0.1
                final_score = similarity * importance_multiplier
                
                scores.append((final_score, node))
        
        # Sort by score desc
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # Return top N descriptions
        return [node.description for score, node in scores[:count]]

    def reflect(self):
        """
        Trigger a reflection process (simplified).
        """
        # This would implement the reflection logic from the paper
        # For now, we just return a placeholder
        return "Reflection triggered (Not fully implemented in this wrapper yet)"
