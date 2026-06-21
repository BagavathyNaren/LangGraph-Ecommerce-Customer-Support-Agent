import random

from locust import HttpUser, between, task


class ECommerceAgentLoadTestUser(HttpUser):
    # Simulated wait time between tasks: 1 to 3 seconds
    wait_time = between(1, 3)

    @task(3)
    def test_health_endpoint(self):
        """Load test the service health check endpoint (essential lightweight ping)."""
        self.client.get("/health")

    @task(2)
    def test_tts_voice_generation(self):
        """Load test the voice generation (TTS) cache performance endpoint."""
        # Query with random text values to trigger cache lookups
        phrases = [
            "Hello! I am your e-commerce assistant.",
            "Certainly! Let me check the order status for you.",
            "Can you please provide your email address?",
            "Your refund has been approved successfully.",
        ]
        text_query = random.choice(phrases)
        self.client.get(f"/tts?text={text_query}")

    @task(1)
    def test_agent_chat_query(self):
        """Load test the main chat LLM agent route using mock inputs."""
        payload = {
            "message": "I want to buy a Playstation in Japan",
            "history": [],
            "userId": "locust-load-test-user-123",
            "voiceEnabled": False,
        }
        self.client.post("/chat", json=payload)
