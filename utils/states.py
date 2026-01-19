from aiogram.fsm.state import State, StatesGroup

class PostWizard(StatesGroup):
     waiting_for_media = State()
     waiting_for_caption = State()
     waiting_for_buttons = State()
     waiting_for_timer = State()
     waiting_for_target = State()
     confirmation = State()
