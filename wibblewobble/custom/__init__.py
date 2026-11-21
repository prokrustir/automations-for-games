from .actions import ChainDrag, RandomChains, SmartChains

# name used in pipeline JSON  ->  action instance
CUSTOM_ACTIONS = {
    "ChainDrag": ChainDrag(),
    "RandomChains": RandomChains(),
    "SmartChains": SmartChains(),
}
