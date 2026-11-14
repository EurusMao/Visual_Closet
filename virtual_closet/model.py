
from threading import RLock
import json
import torch

from transformers import CLIPModel, CLIPProcessor

from .config import MODEL_ID
from .attributes import (
    CATEGORIES,
    COLORS,
    BASE_PATTERNS,
    DECORATIONS,
    SUBCATEGORIES,
    FITS,
    SLEEVE_LENGTHS,
    NECKLINES,
    CLOTHING_LENGTHS,
    UNKNOWN_ATTRIBUTE,
)


class FashionModel:

    def __init__(self):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.lock = RLock()

        self.processor = CLIPProcessor.from_pretrained(
            MODEL_ID, use_fast=False
        )

        self.model = CLIPModel.from_pretrained(
            MODEL_ID, use_safetensors=True
        ).to(self.device).eval()

        self.text_cache = {}

    # ==========================================
    # Feature Extraction
    # ==========================================

    def text_features(self, prompts):
        key = tuple(prompts)

        with self.lock, torch.inference_mode():
            if key not in self.text_cache:

                inputs = self.processor(
                    text=list(prompts),
                    return_tensors='pt',
                    padding=True,
                    truncation=True,
                    max_length=self.model.config.text_config.max_position_embeddings
                ).to(self.device)

                features = self.model.get_text_features(**inputs)

                self.text_cache[key] = (
                    torch.nn.functional.normalize(
                        features, dim=-1
                    ).cpu()
                )

            return self.text_cache[key]

    def image_features(self, image):

        with self.lock, torch.inference_mode():

            inputs = self.processor(
                images=image,
                return_tensors='pt'
            ).to(self.device)

            features = self.model.get_image_features(**inputs)

            return torch.nn.functional.normalize(
                features, dim=-1
            ).cpu()[0]

    # ==========================================
    # Classification Ranking
    # ==========================================

    @staticmethod
    def _rank_with_scores(labels, features, embedding):

        if not labels:
            return [], []

        scores = features @ embedding

        count = min(3, len(labels))

        values, indices = scores.topk(count)

        ranked_labels = [
            labels[i] for i in indices.tolist()
        ]

        ranked_scores = [
            round(float(score), 4)
            for score in values.tolist()
        ]

        return ranked_labels, ranked_scores

    @staticmethod
    def _rank(labels, features, embedding):

        ranked_labels, _ = FashionModel._rank_with_scores(
            labels, features, embedding
        )

        return ranked_labels

    def rank(self, embedding, candidates):

        labels = list(candidates)

        return self._rank(
            labels,
            self.text_features(list(candidates.values())),
            embedding
        )

    # ==========================================
    # Category-aware Attribute Prompts
    # ==========================================

    @staticmethod
    def _attribute_prompts(category):

        upper_categories = {
            'T-shirt',
            'Shirt',
            'Sweater',
            'Hoodie',
            'Jacket',
            'Coat',
            'Dress'
        }

        bottom_categories = {
            'Jeans',
            'Trousers',
            'Shorts',
            'Skirt'
        }

        groups = {}

        # 1. Fit
        if category != 'Shoes':

            groups['Fit'] = {
                key: f'a photo of {category.lower()} with {value}'
                for key, value in FITS.items()
            }

        else:
            groups['Fit'] = {
                UNKNOWN_ATTRIBUTE:
                    'a photo of shoes with unknown fit'
            }

        # 2. Sleeve Length
        if category in upper_categories:

            groups['Sleeve Length'] = {
                key: f'a photo of {category.lower()} with {value}'
                for key, value in SLEEVE_LENGTHS.items()
            }

        else:
            groups['Sleeve Length'] = {
                UNKNOWN_ATTRIBUTE:
                    'clothing with no applicable sleeve length'
            }

        # 3. Neckline
        if category in upper_categories:

            groups['Neckline'] = {
                key: f'a photo of {category.lower()} with {value}'
                for key, value in NECKLINES.items()
            }

        else:
            groups['Neckline'] = {
                UNKNOWN_ATTRIBUTE:
                    'clothing with no applicable neckline'
            }

        # 4. Clothing Length
        if category != 'Shoes':

            groups['Clothing Length'] = {
                key: f'a photo of {category.lower()} with {value}'
                for key, value in CLOTHING_LENGTHS.items()
            }

        else:
            groups['Clothing Length'] = {
                UNKNOWN_ATTRIBUTE:
                    'clothing with no applicable clothing length'
            }

        return groups

    # ==========================================
    # Main Clothing Analysis
    # ==========================================

    def analyze(self, image):

        embedding = self.image_features(image)

        # Step 1: Predict main category
        category_ranks, category_scores = (
            self._rank_with_scores(
                list(CATEGORIES),
                self.text_features(list(CATEGORIES.values())),
                embedding
            )
        )

        category = category_ranks[0]

        # Step 2: Build original attribute groups
        subs = {
            s: f'a photo of {s}'
            for s in SUBCATEGORIES[category]
        }

        subs['Other / unspecified'] = (
            f'a photo of a {category.lower()}'
        )

        groups = {

            'Subcategory': subs,

            'Color': {
                c: f'a photo of a predominantly {c.lower()} {category.lower()}'
                for c in COLORS
            },

            'Base pattern': {
                k: f'a photo of a {category.lower()} whose main outer fabric is {v}'
                for k, v in BASE_PATTERNS.items()
            },

            'Decoration': {
                k: f'a photo of a {category.lower()} with {v}'
                for k, v in DECORATIONS.items()
            }
        }

        # Step 3: Add new attribute groups
        new_groups = self._attribute_prompts(category)

        groups.update(new_groups)

        # Step 4: Prepare all text prompts
        flat_labels = []
        flat_prompts = []
        spans = {}

        for name, candidates in groups.items():

            start = len(flat_labels)

            flat_labels.extend(candidates.keys())
            flat_prompts.extend(candidates.values())

            spans[name] = (
                start,
                len(flat_labels)
            )

        # Step 5: Extract text embeddings
        features = self.text_features(flat_prompts)

        # Step 6: Calculate Top-3 rankings and scores
        rankings = {
            'Category': category_ranks
        }

        similarities = {
            'Category': category_scores
        }

        for name, (start, end) in spans.items():

            labels, scores = self._rank_with_scores(
                flat_labels[start:end],
                features[start:end],
                embedding
            )

            rankings[name] = labels
            similarities[name] = scores

        # Step 7: Save the best prediction for each attribute
        attributes = {
            name: labels[0]
            for name, labels in rankings.items()
        }

        return {
            'attributes': attributes,
            'rankings': rankings,
            'similarities': similarities,
            'embedding': embedding.tolist()
        }

    # ==========================================
    # Occasion Scoring
    # ==========================================

    def occasion_scores(self, items, occasion):

        vectors = torch.tensor(
            [
                json.loads(i['embedding_json'])
                for i in items
            ],
            dtype=torch.float32
        )

        query = self.text_features(
            [f'a photo of clothing for {occasion}']
        )[0]

        return {
            item['id']: float(score)
            for item, score in zip(items, vectors @ query)
        }
