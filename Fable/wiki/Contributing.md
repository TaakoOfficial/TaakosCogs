# 🤝 Contributing to Fable

Thank you for your interest in contributing to Fable! This guide will help you get started with making contributions to the project.

## 🚀 Getting Started

### Setting Up Development Environment

1. **Fork & Clone**

   ```bash
   git clone https://github.com/yourusername/TaakosCogs.git
   cd TaakosCogs
   ```

2. **Install Dependencies**

   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows

   # Install requirements
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Setup Red Dev Environment**

   ```bash
   # Install Red-DiscordBot
   python -m pip install Red-DiscordBot

   # Create test instance
   redbot-setup
   ```

## 💻 Development Guidelines

### Code Style

- Follow **PEP 8** guidelines
- Use **type hints**
- Include **docstrings** for all classes and functions
- Write **clear commit messages**
- Add **tests** for new features

### Structure

```python
from redbot.core import commands, Config
import discord

class YourFeature(commands.Cog):
    """Clear class docstring explaining feature."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=1234567890,
            force_registration=True
        )
```

### Command Implementation

```python
@commands.hybrid_command(
    name="commandname",
    description="Clear command description"
)
@commands.guild_only()
@commands.cooldown(1, 5, commands.BucketType.user)
async def your_command(self, ctx: commands.Context):
    """
    Detailed command description.

    Parameters
    ----------
    ctx: commands.Context
        The command context
    """
    # Command implementation
```

## 📝 Making Changes

### Feature Development

1. **Create Branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**

   - Write clean, documented code
   - Follow existing patterns
   - Test thoroughly

3. **Test Changes**

   ```bash
   # Run tests
   python -m pytest

   # Test in Discord
   redbot YourTestBot --dev
   ```

### Documentation

- Update README.md if needed
- Add wiki documentation
- Include example usage
- Update CHANGELOG.md

## 🧪 Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test
python -m pytest tests/test_your_feature.py

# Run with coverage
python -m pytest --cov=fable
```

### Writing Tests

```python
async def test_your_feature(self):
    """Test description."""
    # Test implementation
    result = await self.cog.your_feature()
    assert result == expected_result
```

## 📚 Contributing Documentation

### Wiki Pages

- Clear, concise writing
- Include examples
- Add screenshots
- Link related pages

### Templates

- Share character templates
- Create location templates
- Design story arc templates
- Document use cases

## 🐛 Bug Reports

### Submitting Issues

1. Check existing issues
2. Use issue template
3. Include:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Error messages
   - Environment details

### Feature Requests

1. Use feature template
2. Explain use case
3. Provide examples
4. Suggest implementation

## 🎨 Design Guidelines

### Embeds

- Use consistent colors
- Follow Discord limits
- Include helpful icons
- Maintain readability

### Command Design

- Clear command names
- Intuitive parameters
- Helpful error messages
- Good user experience

## 📤 Submitting Changes

### Pull Requests

1. Update your fork
2. Create PR
3. Fill template
4. Link related issues

### Review Process

1. Code review
2. Testing
3. Documentation review
4. Final approval

## 🌟 Recognition

### Contributors

- Added to CONTRIBUTORS.md
- Recognized in release notes
- Discord role (if applicable)

### Hall of Fame

- Notable contributions
- Community templates
- Documentation help
- Bug fixes

## 📌 Resources

### Links

- [Discord Server](https://discord.gg/example)
- [Red Documentation](https://docs.discord.red)
- [Discord.py Docs](https://discordpy.readthedocs.io)
- [GitHub Repository](https://github.com/TaakoOfficial/TaakosCogs)

### Templates

- [Issue Templates](.github/ISSUE_TEMPLATE)
- [PR Template](.github/PULL_REQUEST_TEMPLATE.md)
- [Feature Template](.github/FEATURE_TEMPLATE.md)

## 🤝 Community Guidelines

### Code of Conduct

- Be respectful
- Follow guidelines
- Help others
- Stay positive

### Communication

- Clear communication
- Constructive feedback
- Open discussion
- Inclusive environment

---

Thank you for contributing to Fable! Together we can make it even better! 💖
