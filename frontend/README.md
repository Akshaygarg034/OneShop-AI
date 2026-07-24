Smart-Shopping-Assistant/
│
├── backend/
│   │
│   ├── main.py
│   ├── requirements.txt
│   ├── .env
│   ├── README.md
│   │
│   ├── config/
│   │   ├── database.py
│   │   ├── qdrant.py
│   │   ├── llm.py
│   │   ├── settings.py
│   │   └── auth.py
│   │
│   ├── controllers/                  # API Routes
│   │   ├── auth_controller.py
│   │   ├── product_controller.py
│   │   ├── search_controller.py
│   │   ├── chat_controller.py
│   │   ├── recommendation_controller.py
│   │   ├── cart_controller.py
│   │   ├── compare_controller.py
│   │   ├── checkout_controller.py
│   │   ├── profile_controller.py
│   │   └── analytics_controller.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── product_service.py
│   │   ├── search_service.py
│   │   ├── recommendation_service.py
│   │   ├── cart_service.py
│   │   ├── compare_service.py
│   │   ├── checkout_service.py
│   │   ├── profile_service.py
│   │   ├── analytics_service.py
│   │   └── embedding_service.py
│   │
│   ├── agents/                       # AI Agents
│   │   ├── orchestrator.py
│   │   ├── intent_agent.py
│   │   ├── recommendation_agent.py
│   │   ├── search_agent.py
│   │   ├── bundle_agent.py
│   │   ├── cart_agent.py
│   │   ├── compare_agent.py
│   │   ├── explain_agent.py
│   │   ├── profile_agent.py
│   │   └── learning_agent.py
│   │
│   ├── db/
│   │   ├── mysql.py
│   │   ├── qdrant.py
│   │   └── seed_products.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── product.py
│   │   ├── cart.py
│   │   ├── order.py
│   │   ├── chat.py
│   │   ├── recommendation.py
│   │   └── profile.py
│   │
│   ├── repositories/
│   │   ├── user_repository.py
│   │   ├── product_repository.py
│   │   ├── cart_repository.py
│   │   ├── order_repository.py
│   │   └── recommendation_repository.py
│   │
│   ├── prompts/
│   │   ├── recommendation_prompt.py
│   │   ├── search_prompt.py
│   │   ├── explain_prompt.py
│   │   └── bundle_prompt.py
│   │
│   ├── utils/
│   │   ├── auth.py
│   │   ├── jwt.py
│   │   ├── helpers.py
│   │   ├── logger.py
│   │   ├── response.py
│   │   └── constants.py
│   │
│   └── middleware/
│       ├── auth.py
│       └── logging.py
│
├── frontend/
│   │
│   ├── src/
│   │
│   ├── pages/
│   │   ├── Home
│   │   ├── Login
│   │   ├── Signup
│   │   ├── Product Details
│   │   ├── Cart
│   │   ├── Orders
│   │   ├── Profile
│   │   └── Checkout
│   │
│   ├── components/
│   │   ├── Navbar
│   │   ├── Search Bar
│   │   ├── Product Card
│   │   ├── Recommendation Carousel
│   │   ├── AI Chat Widget
│   │   ├── Bundle Suggestions
│   │   ├── Compare Products
│   │   ├── Cart Sidebar
│   │   └── Footer
│   │
│   ├── services/
│   │   ├── authApi.js
│   │   ├── chatApi.js
│   │   ├── cartApi.js
│   │   ├── productApi.js
│   │   └── recommendationApi.js
│   │
│   ├── context/
│   │   ├── AuthContext
│   │   ├── CartContext
│   │   └── UserContext
│   │
│   └── assets/
│
└── docs/
    ├── architecture.md
    ├── database_schema.md
    ├── api_design.md
    └── sequence_diagrams.md


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