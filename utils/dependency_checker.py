"""
Dependency checker for the modular ANSV bot architecture.
Validates that all required dependencies are available and provides fallback options.
"""

import logging
import sys
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DependencyInfo:
    """Information about a dependency."""
    name: str
    required: bool
    fallback_available: bool
    error_message: Optional[str] = None
    install_command: Optional[str] = None


def check_dependencies() -> Tuple[bool, List[DependencyInfo]]:
    """Check all dependencies and return status and detailed info."""
    dependencies = []
    all_critical_available = True
    
    # Core dependencies
    deps_to_check = [
        # Critical dependencies
        ("sqlite3", True, False, None, "Built into Python"),
        ("asyncio", True, False, None, "Built into Python"),
        ("logging", True, False, None, "Built into Python"),
        ("configparser", True, False, None, "Built into Python"),
        
        # External critical dependencies
        ("twitchio", True, False, None, "pip install twitchio"),
        
        # Performance dependencies
        ("aiosqlite", False, True, "Async database operations will use sync fallback", "pip install aiosqlite"),
        
        # Optional TTS dependencies
        ("markovify", False, True, "Markov text generation disabled", "pip install markovify"),
        ("nltk", False, True, "Advanced text processing disabled", "pip install nltk"),
        ("bark", False, True, "Bark TTS disabled", "pip install bark"),
        ("torch", False, True, "PyTorch-based features disabled", "pip install torch"),
        ("transformers", False, True, "Transformer models disabled", "pip install transformers"),
        ("numpy", False, True, "NumPy operations disabled", "pip install numpy"),
        ("scipy", False, True, "SciPy operations disabled", "pip install scipy"),
    ]
    
    for dep_name, required, fallback, fallback_msg, install_cmd in deps_to_check:
        try:
            __import__(dep_name)
            dep_info = DependencyInfo(
                name=dep_name,
                required=required,
                fallback_available=fallback,
                install_command=install_cmd
            )
            dependencies.append(dep_info)
        except ImportError as e:
            dep_info = DependencyInfo(
                name=dep_name,
                required=required,
                fallback_available=fallback,
                error_message=str(e),
                install_command=install_cmd
            )
            dependencies.append(dep_info)
            
            if required:
                all_critical_available = False
                logging.error(f"Critical dependency missing: {dep_name}")
            else:
                logging.warning(f"Optional dependency missing: {dep_name} - {fallback_msg}")
    
    return all_critical_available, dependencies


def validate_environment() -> bool:
    """Validate the entire environment for running the modular bot."""
    logging.info("Validating environment for ANSV bot...")
    
    # Check Python version
    if sys.version_info < (3, 7):
        logging.error("Python 3.7+ is required")
        return False
    
    # Check dependencies
    critical_ok, deps = check_dependencies()
    
    if not critical_ok:
        logging.error("Critical dependencies missing - bot cannot start")
        return False
    
    # Check for recommended dependencies
    missing_recommended = [dep for dep in deps if not dep.error_message and not dep.required]
    if missing_recommended:
        logging.info(f"Recommended dependencies available: {len(missing_recommended)}")
    
    missing_optional = [dep for dep in deps if dep.error_message and not dep.required]
    if missing_optional:
        logging.warning(f"Optional dependencies missing: {len(missing_optional)} (degraded functionality)")
    
    return True


def get_installation_instructions() -> str:
    """Get installation instructions for missing dependencies."""
    _, deps = check_dependencies()
    missing_deps = [dep for dep in deps if dep.error_message]
    
    if not missing_deps:
        return "All dependencies are satisfied!"
    
    instructions = ["Missing dependencies found:", ""]
    
    critical_missing = [dep for dep in missing_deps if dep.required]
    optional_missing = [dep for dep in missing_deps if not dep.required]
    
    if critical_missing:
        instructions.append("CRITICAL (required for bot to work):")
        for dep in critical_missing:
            instructions.append(f"  ❌ {dep.name}: {dep.install_command}")
        instructions.append("")
    
    if optional_missing:
        instructions.append("OPTIONAL (for enhanced functionality):")
        for dep in optional_missing:
            instructions.append(f"  ⚠️  {dep.name}: {dep.install_command}")
        instructions.append("")
    
    instructions.extend([
        "Quick install for all missing dependencies:",
        "pip install twitchio aiosqlite markovify nltk numpy scipy",
        "",
        "For TTS functionality (larger install):",
        "pip install torch transformers bark-voice",
    ])
    
    return "\n".join(instructions)


def get_fallback_configuration() -> Dict[str, bool]:
    """Get configuration for fallback modes based on available dependencies."""
    _, deps = check_dependencies()
    dep_status = {dep.name: dep.error_message is None for dep in deps}
    
    return {
        "async_database": dep_status.get("aiosqlite", False),
        "markov_enabled": dep_status.get("markovify", False),
        "tts_enabled": all([
            dep_status.get("torch", False),
            dep_status.get("transformers", False),
            dep_status.get("bark", False)
        ]),
        "advanced_text_processing": dep_status.get("nltk", False),
        "numpy_operations": dep_status.get("numpy", False),
    }


if __name__ == "__main__":
    print("ANSV Bot Dependency Checker")
    print("=" * 50)
    
    if validate_environment():
        print("✅ Environment validation passed!")
        
        config = get_fallback_configuration()
        print("\nFeature availability:")
        for feature, available in config.items():
            status = "✅" if available else "❌"
            print(f"  {status} {feature}")
    else:
        print("❌ Environment validation failed!")
        print("\n" + get_installation_instructions())