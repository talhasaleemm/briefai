import os
import re
import io

replacements = [
    (r'from app\.core\.config', 'from briefai.config'),
    (r'import app\.core\.config', 'import briefai.config'),
    (r'app\.core\.config', 'briefai.config'),
    
    (r'from app\.core\.database', 'from briefai.internal.db'),
    (r'import app\.core\.database', 'import briefai.internal.db'),
    (r'app\.core\.database', 'briefai.internal.db'),
    
    (r'from app\.core\.security', 'from briefai.utils.security'),
    (r'import app\.core\.security', 'import briefai.utils.security'),
    (r'app\.core\.security', 'briefai.utils.security'),
    
    (r'from app\.core\.limiter', 'from briefai.utils.limiter'),
    (r'import app\.core\.limiter', 'import briefai.utils.limiter'),
    (r'app\.core\.limiter', 'briefai.utils.limiter'),
    
    (r'from app\.api\.deps', 'from briefai.utils.deps'),
    (r'import app\.api\.deps', 'import briefai.utils.deps'),
    (r'app\.api\.deps', 'briefai.utils.deps'),
    
    (r'from app\.api', 'from briefai.routers'),
    (r'import app\.api', 'import briefai.routers'),
    
    (r'from app\.services\.rag_service', 'from briefai.retrieval.rag_service'),
    (r'import app\.services\.rag_service', 'import briefai.retrieval.rag_service'),
    
    (r'from app\.models\.database', 'from briefai.models'),
    (r'import app\.models\.database', 'import briefai.models'),
    
    (r'from app\.models\.schemas', 'from briefai.schemas'),
    (r'import app\.models\.schemas', 'import briefai.schemas'),
    
    (r'from app\.', 'from briefai.'),
    (r'import app\.', 'import briefai.'),
    (r'from app ', 'from briefai '),
]

def process_file(path):
    with io.open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements:
        new_content = re.sub(old, new, new_content)
        
    if new_content != content:
        with io.open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Updated: " + path)

for root, _, files in os.walk('backend'):
    if 'venv' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py') or file == 'alembic.ini':
            process_file(os.path.join(root, file))
