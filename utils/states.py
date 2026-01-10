from aiogram.fsm.state import State, StatesGroup

class PostWizard(StatesGroup):
    waiting_for_media = State()   # Photo/Video ka wait
    waiting_for_caption = State() # Text ka wait
    waiting_for_buttons = State() # Buttons ka wait
    waiting_for_timer = State()   # Delete timer ka wait
    confirmation = State()        # Final Yes/No
