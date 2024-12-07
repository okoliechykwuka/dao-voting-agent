from pydantic import BaseModel


# Models
class CreateProposalRequest(BaseModel):
    title: str
    description: str
    private_key: str

class VoteRequest(BaseModel):
    proposal_id: int
    private_key: str

class TransactionResponse(BaseModel):
    transaction_hash: str
    
class BalanceResponse(BaseModel):
    balance: float

class VoteHistoryResponse(BaseModel):
    voted_proposals: list
    
class ProposalResponse(BaseModel):
    proposal_id: int
    title: str
    description: str
    vote_count: int
    executed: bool

class AllProposalsResponse(BaseModel):
    proposals: list[ProposalResponse]
    
    
################  AGENT MODELS #######################

class AnalyzeProposalRequest(BaseModel):
    title: str
    description: str

class AnalyzeProposalResponse(BaseModel):
    analysis: str

class ChatRequest(BaseModel):
    message: str
    user_address: str  # User's Ethereum address for context

class ChatResponse(BaseModel):
    reply: str