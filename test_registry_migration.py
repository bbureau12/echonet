#!/usr/bin/env python3
"""
Quick test script to verify the SQLite registry implementation.
Run this to ensure the migration from in-memory to SQLite works correctly.
"""

from app.registry import Target, TargetRegistryRepository
from app.migrations import run_migrations
import os
import tempfile


def test_registry():
    """Test basic registry operations with SQLite backend."""
    # Use a temporary database for testing
    test_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    test_db.close()
    
    try:
        print("🧪 Testing SQLite Registry Implementation")
        print("=" * 50)
        
        # Run migrations first
        print("Running migrations...")
        run_migrations(test_db.name)
        print("✅ Migrations completed")
        
        # Initialize registry
        registry = TargetRegistryRepository(db_path=test_db.name)
        print("✅ Registry initialized")
        
        # Test upsert
        target1 = Target(
            name="astraea",
            base_url="http://astraea.local:9001",
            phrases=["hey astraea", "hello astraea"]
        )
        registry.upsert(target1)
        print(f"✅ Upserted target: {target1.name}")
        
        target2 = Target(
            name="echobell",
            base_url="http://echobell.local:9000",
            phrases=["hey echo", "hello echo bell"]
        )
        registry.upsert(target2)
        print(f"✅ Upserted target: {target2.name}")
        
        # Test get
        retrieved = registry.get("astraea")
        assert retrieved is not None
        assert retrieved.name == "astraea"
        assert retrieved.base_url == target1.base_url
        assert retrieved.phrases == target1.phrases
        print(f"✅ Retrieved target: {retrieved.name}")
        
        # Test case-insensitive get
        retrieved_upper = registry.get("ASTRAEA")
        assert retrieved_upper is not None
        assert retrieved_upper.name == "astraea"
        print("✅ Case-insensitive get works")
        
        # Test all
        all_targets = registry.all()
        assert len(all_targets) == 2
        print(f"✅ Retrieved all targets: {len(all_targets)} targets")
        
        # Test phrase_map
        phrase_map = registry.phrase_map()
        assert len(phrase_map) == 4  # 2 phrases per target
        print(f"✅ Phrase map generated: {len(phrase_map)} phrases")
        for phrase, target_name in phrase_map:
            print(f"   - '{phrase}' → {target_name}")
        
        # Test update (upsert existing)
        target1_updated = Target(
            name="astraea",
            base_url="http://astraea.local:9002",  # Changed port
            phrases=["hey astraea", "hello astraea", "hi astraea"]  # Added phrase
        )
        registry.upsert(target1_updated)
        retrieved_updated = registry.get("astraea")
        assert retrieved_updated.base_url == "http://astraea.local:9002"
        assert len(retrieved_updated.phrases) == 3
        print("✅ Update (upsert) works correctly")
        
        # Test delete
        deleted = registry.delete("echobell")
        assert deleted is True
        assert registry.get("echobell") is None
        print("✅ Delete works correctly")
        
        # Test delete non-existent
        deleted_again = registry.delete("nonexistent")
        assert deleted_again is False
        print("✅ Delete non-existent returns False")
        
        # Test persistence - create new registry instance with same DB
        registry2 = TargetRegistryRepository(db_path=test_db.name)
        persisted = registry2.get("astraea")
        assert persisted is not None
        assert persisted.base_url == "http://astraea.local:9002"
        assert len(persisted.phrases) == 3
        print("✅ Persistence across instances works")
        
        print("=" * 50)
        print("🎉 All tests passed! SQLite registry is working correctly.")
        
    finally:
        # Cleanup - on Windows, we need to give the DB time to close
        import time
        time.sleep(0.1)
        try:
            if os.path.exists(test_db.name):
                os.unlink(test_db.name)
                print(f"🧹 Cleaned up test database: {test_db.name}")
        except PermissionError:
            print(f"ℹ️  Note: Could not delete test DB (Windows file lock). File: {test_db.name}")


if __name__ == "__main__":
    test_registry()
