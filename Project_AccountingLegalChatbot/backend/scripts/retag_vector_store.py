"""
Bulk re-tag existing ChromaDB chunks with correct domain metadata.

Fetches every chunk from ChromaDB, runs infer_domain_from_name(original_name),
and updates the 'domain' metadata if it has changed.

Usage:
    python backend/scripts/retag_vector_store.py --dry-run
    python backend/scripts/retag_vector_store.py --apply
"""

import sys
import argparse
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from core.rag_engine import rag_engine
from core.domains import infer_domain_from_name

def main():
    parser = argparse.ArgumentParser(description="Retag ChromaDB chunks with correct domain.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to ChromaDB.")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("Please specify either --dry-run or --apply.")
        return

    collection = rag_engine.collection
    total_count = collection.count()
    print(f"Total chunks in collection: {total_count}")

    batch_size = 1000
    offset = 0
    updated_count = 0
    processed_count = 0
    domain_changes = {} # (old_domain, new_domain) -> count

    while offset < total_count:
        batch = collection.get(
            include=["metadatas"],
            limit=batch_size,
            offset=offset
        )
        
        ids = batch["ids"]
        metadatas = batch["metadatas"]
        
        if not ids:
            break
            
        batch_to_update_ids = []
        batch_to_update_metas = []
        
        for i, meta in zip(ids, metadatas):
            processed_count += 1
            original_name = meta.get("original_name", "")
            current_domain = meta.get("domain", "unknown")
            
            if not original_name:
                # Try to infer from source if original_name is missing
                original_name = meta.get("source", "")
                
            new_domain = infer_domain_from_name(original_name)
            
            if current_domain != new_domain:
                updated_count += 1
                change_key = (current_domain, new_domain)
                domain_changes[change_key] = domain_changes.get(change_key, 0) + 1
                
                new_meta = dict(meta)
                new_meta["domain"] = new_domain
                batch_to_update_ids.append(i)
                batch_to_update_metas.append(new_meta)
        
        if args.apply and batch_to_update_ids:
            try:
                collection.update(
                    ids=batch_to_update_ids,
                    metadatas=batch_to_update_metas
                )
            except Exception as e:
                print(f"Error updating batch at offset {offset}: {e}")
            
        offset += batch_size
        print(f"Processed {processed_count}/{total_count} chunks...")

    print("\nRe-tagging Summary:")
    print(f"  Total chunks processed: {processed_count}")
    print(f"  Total chunks needing update: {updated_count}")
    
    if domain_changes:
        print("\nChanges breakdown:")
        for (old, new), count in sorted(domain_changes.items(), key=lambda x: x[1], reverse=True):
            print(f"  {old} -> {new}: {count} chunks")
    else:
        print("\nNo domain changes detected.")

    if args.dry_run:
        print("\nDry-run complete. No changes were applied.")
    elif args.apply:
        print(f"\nApplied updates to {updated_count} chunks.")

if __name__ == "__main__":
    main()
