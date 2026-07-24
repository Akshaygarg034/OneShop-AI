                        +----------------------+
                        |      User (Web)      |
                        +----------+-----------+
                                   |
                        React / Next.js Frontend
                                   |
        -----------------------------------------------------
        |                   |                 |              |
    Product Grid        Search Bar      AI Chat Widget    Cart
        |                   |                 |              |
        -----------------------------------------------------
                                   |
                             FastAPI Backend
                                   |
    -------------------------------------------------------------------
    |              |              |             |            |          |
 Auth API     Product API     Chat API     Cart API    Order API   Analytics
                                   |
                           AI Orchestrator (Agent)
                                   |
    -------------------------------------------------------------------------
    |             |             |            |             |                |
 Intent      Recommendation   Search      Cart Agent   Profile Agent   Explain Agent
 Agent          Agent          Agent
                                   |
                         LLM (OpenAI/Gemini)
                                   |
        -----------------------------------------------------------
        |                    |                 |                   |
     MySQL              Qdrant DB         Redis Cache         Analytics DB