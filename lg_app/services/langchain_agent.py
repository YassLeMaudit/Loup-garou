from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional, Tuple, Callable

from langchain.agents import AgentExecutor, create_structured_chat_agent, create_tool_calling_agent
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, FunctionMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, create_model

from . import agent_runtime, agent_tools, llm_gm
from langchain_core.runnables import Runnable, RunnablePassthrough
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.messages import FunctionMessage
from langchain_core.exceptions import OutputParserException
from langchain_core.prompts import BasePromptTemplate
from langchain_core.output_parsers import JsonOutputParser


def _schema_type_to_python(schema: Dict[str, str]) -> Tuple[type, Dict[str, object]]:
    type_name = schema.get("type", "string")
    description = schema.get("description", "")
    python_type: type
    if type_name == "integer":
        python_type = int
    elif type_name == "boolean":
        python_type = bool
    else:
        python_type = str
    field_kwargs: Dict[str, object] = {"description": description}
    return python_type, field_kwargs


def _build_args_model(name: str, parameters: Dict[str, object]) -> BaseModel:
    properties: Dict[str, Dict[str, str]] = parameters.get("properties", {})  # type: ignore[assignment]
    required = set(parameters.get("required", [])) if parameters else set()  # type: ignore[arg-type]
    fields: Dict[str, Tuple[type, Field]] = {}
    for prop_name, spec in properties.items():
        python_type, meta = _schema_type_to_python(spec)
        if prop_name in required:
            default = ...
        else:
            default = None
        fields[prop_name] = (python_type, Field(default=default, **meta))
    model_name = "".join(part.capitalize() for part in name.split("_")) + "Args"
    if not fields:
        return create_model(model_name)  # type: ignore[return-value]
    return create_model(model_name, **fields)  # type: ignore[return-value]


def _wrap_tool(identifier: str, func: Callable[..., str]) -> Callable[..., BaseMessage]:
    def _tool(**kwargs: object) -> BaseMessage:
        try:
            return AIMessage(content=func(**kwargs))
        except agent_runtime.AgentToolError as exc:
            context = agent_runtime.get_current_context()
            context.errors.append(str(exc))
            return AIMessage(content=f"Erreur: {exc}")
    _tool.__name__ = identifier
    return _tool


def _build_tools() -> List[StructuredTool]:
    tools: List[StructuredTool] = []
    for spec in agent_tools.TOOL_DEFINITIONS:
        name = spec["name"]
        params = spec.get("parameters", {}) or {}
        description = spec.get("description", "")
        args_model = _build_args_model(name, params)  # type: ignore[arg-type]
        base_func = agent_runtime.TOOL_FUNCTIONS[name]

        def _bound_func(base=base_func, tool_name=name, model=args_model):
            def inner(**kwargs: object) -> str:
                context = agent_runtime.get_current_context()
                filtered_kwargs = {
                    key: value
                    for key, value in kwargs.items()
                    if key in model.model_fields and value is not None
                }
                return base(**filtered_kwargs)

            return inner

        tool_callable = _wrap_tool(name, _bound_func())
        tools.append(
            StructuredTool.from_function(
                tool_callable,
                name=name,
                description=description,
                args_schema=args_model,
            )
        )
    return tools


def _build_agent_executor() -> AgentExecutor:
    tools = _build_tools()
    llm = ChatGoogleGenerativeAI(
        model=llm_gm.DEFAULT_MODEL,
        temperature=0.2,
        max_output_tokens=450,
    )
    system_prompt = (
        "Tu es le maître du jeu du Loup-Garou. Utilise exclusivement les outils fournis pour modifier la partie. "
        "Décris brièvement les actions réalisées, rappelle la phase en cours et les conséquences pour les joueurs. "
        "Si une action échoue, explique clairement le problème et propose une alternative.\n\n"
        "Outils disponibles : {tool_names}\n{tools}"
    )
    tool_names = ", ".join([tool.name for tool in tools])
    formatted_tools = "\n".join(
        f"{tool.name}: {tool.description}" for tool in tools
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    prompt = prompt.partial(tool_names=tool_names, tools=formatted_tools)
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, handle_parsing_errors=True, verbose=True)


def process_message(
    game_code: Optional[str],
    chat_history: List[Dict[str, str]],
    user_message: str,
) -> agent_runtime.AgentResponse:
    context = agent_runtime.AgentContext(
        game_code=game_code,
        chat_history=chat_history,
        user_message=user_message,
    )
    token = agent_runtime.set_current_context(context)
    executor = _build_agent_executor()
    lc_history: List[object] = []
    for message in chat_history:
        if message["role"] == "user":
            lc_history.append(HumanMessage(content=message["content"]))
        else:
            lc_history.append(AIMessage(content=message["content"]))
    result = executor.invoke(
        {
            "input": user_message,
            "chat_history": lc_history,
            "agent_scratchpad": []
        }
    )
    assistant_reply = result.get("output", "").strip()
    if not assistant_reply:
        assistant_reply = "Je n'ai pas pu générer de réponse pour le moment."

    return agent_runtime.persist_interaction(context, assistant_reply)
