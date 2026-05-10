from pydantic import BaseModel, Field
from typing import List



# thoughts: str = Field(
#         ...,
#         description="Pensamentos e Observações gerados durante a execução"
#     )

"""
A Task representa a tarefa refinada, que é uma descrição clara e objetiva do que precisa ser feito,
junto com a intenção do usuário resumida em uma frase. Essa estrutura é fundamental para orientar
a execução do plano de pesquisa e a coleta de contexto, garantindo que todas as ações estejam alinhadas
com o objetivo final do usuário.
"""
class Task(BaseModel):
    description: str = Field(
        ...,
        description="Descrição clara e objetiva da tarefa refinada"
    )
    intent: str = Field(
        ...,
        description="Intenção do usuário resumida em uma frase"
    )


class PlanItem(BaseModel):
    quick_description: str = Field(
        ...,
        description="Descrição curta e direta da ação a ser executada"
    )
    detailed_description: str = Field(
        ...,
        description="Descrição detalhada da ação, incluindo como executar e o que se espera obter"
    )
    tools_suggestions: List[str] = Field(
        default_factory=list,
        description="Lista de ferramentas sugeridas para executar a ação"
    )

"""
O ResearchPlan é uma estrutura que organiza as etapas de execução para a coleta de contexto.
Cada PlanItem representa uma ação específica a ser realizada, com uma descrição rápida para referência 
e uma descrição detalhada para orientação.
"""
class ResearchPlan(BaseModel):
    steps: List[PlanItem] = Field(
        default_factory=list,
        description="Etapas ordenadas de execução para coleta de contexto"
    )   

"""
O ContextItem representa uma peça de informação coletada durante a execução do plano de pesquisa. 
Ele inclui um título curto para resumir a informação, o conteúdo relevante coletado 
e a fonte de onde essa informação foi obtida. O Context é uma coleção desses itens, 
organizados em uma lista, que serve como base para a execução da tarefa refinada.
""" 
class ContextItem(BaseModel):
    title: str = Field(
        ...,
        description="Título curto que resume a informação coletada"
    )
    content: str = Field(
        ...,
        description="Conteúdo relevante coletado"
    )
    source: str = Field(
        ...,
        description="Origem da informação (ex: ferramenta ou fonte)"
    )


class Context(BaseModel):
    items: List[ContextItem] = Field(
        default_factory=list,
        description="Lista de contextos coletados"
    )

"""
ExecutionPlan é a estrutura que organiza as etapas de execução para a realização da tarefa refinada,
com base no contexto coletado. Cada PlanItem representa uma ação específica a ser realizada,
com uma descrição rápida para referência e uma descrição detalhada para orientação, além de sugestões de ferramentas
que podem ser utilizadas para executar a ação. O ExecutionPlan é essencial para garantir que a execução da tarefa
esteja alinhada com o objetivo do usuário e que todas as ações sejam realizadas de forma eficiente e eficaz.
"""

class ExecutionPlan(BaseModel):
    steps: List[PlanItem] = Field(
        default_factory=list,
        description="Etapas ordenadas para execução"
    )


class UsedTool(BaseModel):
    name: str = Field(
        ...,
        description="Nome da ferramenta utilizada"
    )
    description: str = Field(
        ...,
        description="Descrição do que a ferramenta fez"
    )

"""
Será usado para a consolidação dos resultados da execução, onde serão listadas as ferramentas utilizadas,
os problemas ou limitações encontrados durante a execução, uma mensagem final consolidada que será entregue ao usuário
e um texto sugerindo próximos passos para o usuário. Essa estrutura é fundamental para fornecer um feedback claro e útil ao usuário,
ajudando-o a entender o que foi feito, quais foram os resultados e quais são as próximas ações recomendadas.
"""

class RunResults(BaseModel):
    used_tools: List[UsedTool] = Field(
        default_factory=list,
        description="Lista de ferramentas utilizadas durante a execução"
    )
    detected_problems: List[str] = Field(
        default_factory=list,
        description="Problemas ou limitações encontrados durante a execução"
    )
    results_consolidation: str = Field(
        ...,
        description="Mensagem final consolidada que será entregue ao usuário"
    )
    next_steps: str = Field(
        ...,
        description="Texto sugerindo próximos passos para o usuário"
    )


class IsStepComplete(BaseModel):
    """Indica se um passo foi executado corretamente"""
    isComplete: bool = Field(description="Indica se o passo foi finalizado.")
    error: bool = Field(description="Indica se houve erro na execução do passo.")
    motif: str = Field(description="Motivo do erro, se houver.")