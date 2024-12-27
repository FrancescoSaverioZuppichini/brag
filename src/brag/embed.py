from typing import Optional

import torch
import torch.nn.functional as F

from .schemas import Document, FileDocument, URLDocument
from pdf2image import convert_from_path
from PIL import Image
from torch.utils.data import DataLoader
from tqdm import tqdm
import multiprocessing

from colpali_engine.models import (
    ColQwen2,
    ColQwen2Processor,
    ColIdefics3,
    ColIdefics3Processor,
)
from typing import TypedDict, Union
from PIL import Image
from .logger import logger

device = "cuda:0" if torch.cuda.is_available() else "cpu"


def _embed(
    model: ColIdefics3,
    dataloader: DataLoader,
) -> torch.Tensor:
    if device != model.device:
        model.to(device)
    embeddings = []
    for batch_doc in tqdm(dataloader):
        with torch.no_grad():
            embeddings_doc = model(**batch_doc)
        embeddings.append(embeddings_doc)
    embeddings_pt = torch.cat(embeddings)
    return embeddings_pt 


def embed_images(
    model: ColIdefics3,
    processor: ColIdefics3Processor,
    images: list[Image.Image],
    batch_size: Optional[int] = 1,
) -> list[torch.Tensor]:
    # if document is a string, we make a couple of assumption to see if it is a url
    # if isinstance(document, str):
    #     if document[0:4] == "http":
    #         document = URLDocument(url=document)
    #     else:
    #         document = FileDocument(path=document)
    dataloader = DataLoader(
        images,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=lambda x: processor.process_images(x).to(model.device),
    )
    embeddings = _embed(model, dataloader)
    return embeddings 

def embed_query(
    model: ColIdefics3,
    processor: ColIdefics3Processor,
    query: str
):
    if device != model.device:
        model.to(device)
    with torch.no_grad():
        batch_query = processor.process_queries([query]).to(model.device)
        embeddings_query = model(**batch_query)
    return embeddings_query

def retrieve(
    model: ColIdefics3,
    processor: ColIdefics3Processor,
    query: str,
    embeddings: torch.Tensor,
    k: int = 4,
):
    embeddings_query = embed_query(model, processor, query)

    scores = processor.score(embeddings_query, embeddings, device=device)

    top_k_values, top_k_indices = scores.topk(k, dim=1)

    results = [
        [(idx, value, idx) for idx, value in zip(indices.tolist(), values.tolist())]
        for indices, values in zip(top_k_indices.cpu(), top_k_values.cpu())
    ]

    return results
