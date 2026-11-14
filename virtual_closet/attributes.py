
# Main clothing categories
CATEGORIES = {
    'T-shirt': 'a photo of a t-shirt',
    'Shirt': 'a photo of a button-up shirt',
    'Sweater': 'a photo of a sweater',
    'Hoodie': 'a photo of a hoodie',
    'Jacket': 'a photo of a jacket',
    'Coat': 'a photo of a coat',
    'Jeans': 'a photo of jeans',
    'Trousers': 'a photo of trousers',
    'Shorts': 'a photo of shorts',
    'Skirt': 'a photo of a skirt',
    'Dress': 'a photo of a dress',
    'Shoes': 'a photo of shoes'
}


# Clothing colors
COLORS = [
    'Black', 'White', 'Gray', 'Blue', 'Navy',
    'Red', 'Green', 'Yellow', 'Pink', 'Purple',
    'Brown', 'Beige', 'Khaki', 'Orange'
]


# Clothing patterns
BASE_PATTERNS = {
    'Solid': 'plain solid-colored fabric',
    'Striped': 'striped fabric',
    'Plaid': 'plaid checkered fabric',
    'Floral': 'all-over floral patterned fabric',
    'Polka dot': 'polka dot patterned fabric',
    'Animal print': 'animal print fabric',
    'Camouflage': 'camouflage patterned fabric'
}


# Clothing decorations
DECORATIONS = {
    'None': 'no visible logo, embroidery, or printed graphic',
    'Small logo': 'a small visible logo',
    'Large printed graphic': 'a large printed graphic',
    'Decorative embroidery': 'decorative embroidery',
    'Text print': 'printed lettering or text'
}


# Clothing subcategories
SUBCATEGORIES = {
    'T-shirt': [
        'crew-neck t-shirt',
        'v-neck t-shirt',
        'polo shirt'
    ],
    'Shirt': [
        'oxford shirt',
        'dress shirt',
        'flannel shirt',
        'denim shirt',
        'overshirt'
    ],
    'Sweater': [
        'crew-neck sweater',
        'v-neck sweater',
        'turtleneck sweater',
        'cardigan'
    ],
    'Hoodie': [
        'pullover hoodie',
        'zip-up hoodie'
    ],
    'Jacket': [
        'denim jacket',
        'bomber jacket',
        'leather jacket',
        'puffer jacket',
        'blazer',
        'windbreaker'
    ],
    'Coat': [
        'car coat',
        'trench coat',
        'overcoat',
        'pea coat',
        'parka',
        'duffle coat'
    ],
    'Jeans': [
        'straight-leg jeans',
        'skinny jeans',
        'wide-leg jeans',
        'bootcut jeans'
    ],
    'Trousers': [
        'chino pants',
        'dress trousers',
        'cargo pants',
        'joggers',
        'corduroy pants'
    ],
    'Shorts': [
        'chino shorts',
        'denim shorts',
        'cargo shorts',
        'athletic shorts'
    ],
    'Skirt': [
        'pleated skirt',
        'pencil skirt',
        'a-line skirt',
        'wrap skirt'
    ],
    'Dress': [
        'shirt dress',
        'wrap dress',
        'slip dress',
        'sweater dress'
    ],
    'Shoes': [
        'sneakers',
        'loafers',
        'boots',
        'sandals',
        'dress shoes',
        'heels'
    ]
}


# ==================================================
# NEW: Additional clothing attributes
# ==================================================

# 1. Clothing Fit
FITS = {
    'Oversized': 'an oversized fit',
    'Loose': 'a loose fit',
    'Relaxed': 'a relaxed fit',
    'Regular': 'a regular fit',
    'Slim': 'a slim fit',
    'Fitted': 'a close fitted silhouette',
    'Unknown': 'a fit that cannot be determined from the image'
}


# 2. Sleeve Length
SLEEVE_LENGTHS = {
    'Sleeveless': 'sleeveless clothing',
    'Cap Sleeve': 'clothing with cap sleeves',
    'Short Sleeve': 'clothing with short sleeves',
    'Three-quarter Sleeve': 'clothing with three-quarter sleeves',
    'Long Sleeve': 'clothing with long sleeves',
    'Unknown': 'sleeve length that cannot be determined from the image'
}


# 3. Neckline
NECKLINES = {
    'Crew Neck': 'a crew neckline',
    'V-neck': 'a V-shaped neckline',
    'Turtleneck': 'a turtleneck neckline',
    'Collared': 'a collared neckline',
    'Scoop Neck': 'a scoop neckline',
    'Square Neck': 'a square neckline',
    'Off-shoulder': 'an off-shoulder neckline',
    'Unknown': 'a neckline that cannot be determined from the image'
}


# 4. Clothing Length
CLOTHING_LENGTHS = {
    'Cropped': 'a cropped length',
    'Regular': 'a regular clothing length',
    'Long': 'a long clothing length',
    'Unknown': 'a clothing length that cannot be determined from the image'
}


# Shared unknown label for attributes without a reliable prediction
UNKNOWN_ATTRIBUTE = 'Unknown'
