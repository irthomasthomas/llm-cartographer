from setuptools import setup, find_packages

setup(
    name="llm-cartographer",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "llm>=0.5.0",
        "click>=8.0.0",
        "pathspec>=0.11.0",
        "rich>=13.0.0",
        "tqdm>=4.64.0",
        "colorama>=0.4.6"
    ],
    entry_points={
        "llm": [
            "cartographer=llm_cartographer",
        ],
    },
    author="Thomas Thomas",
    author_email="author@example.com",
    description="A plugin for mapping and describing a codebase or project",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/llm-cartographer",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
)
