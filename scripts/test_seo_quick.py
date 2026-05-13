#!/usr/bin/env python3
"""Quick test for SEO processor."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from content_aggregator.processors.seo import SEOProcessor, SEOConfig, SEOResult
    
    print("✅ SEO module imported successfully")
    
    # Test instantiation
    config = SEOConfig()
    print(f"✅ SEOConfig created: keywords_count={config.keywords_count}")
    
    processor = SEOProcessor(config)
    print(f"✅ SEOProcessor instantiated")
    
    print("\n🎉 All basic tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
