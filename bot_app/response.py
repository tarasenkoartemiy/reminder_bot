import json


def opener(*args, **kwargs):
    with open(f"bot_app/{kwargs['language']}.json", encoding="utf-8") as json_data:
        dict_data = json.load(json_data)
        for i in args:
            dict_data = dict_data[i]
    return dict_data


def context_gen(*args, language, other=None):
    context = {subsection: message for subsection, message in opener(*args, language=language).items()}
    if other:
        for key, value in other.items():
            context[key] = value
        return context
    return context
