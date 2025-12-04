# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet
from datetime import datetime, timedelta
import pytz
import re


def korean_number_to_int(text: str) -> int:
    """Convert Korean number words to integers."""
    # 한국어 숫자 매핑
    korean_numbers = {
        '영': 0, '공': 0,
        '하나': 1, '한': 1, '일': 1,
        '둘': 2, '두': 2, '이': 2,
        '셋': 3, '세': 3, '삼': 3,
        '넷': 4, '네': 4, '사': 4,
        '다섯': 5, '오': 5,
        '여섯': 6, '육': 6, '륙': 6,
        '일곱': 7, '칠': 7,
        '여덟': 8, '팔': 8,
        '아홉': 9, '구': 9,
        '열': 10, '십': 10,
        '스물': 20, '이십': 20,
        '서른': 30, '삼십': 30,
        '마흔': 40, '사십': 40,
        '쉰': 50, '오십': 50,
        '예순': 60, '육십': 60,
        '일흔': 70, '칠십': 70,
        '여든': 80, '팔십': 80,
        '아흔': 90, '구십': 90,
        '백': 100, '천': 1000,
    }

    text = text.strip()

    # 먼저 숫자인지 확인
    if text.isdigit():
        return int(text)

    # 한국어 숫자 매핑에서 찾기
    if text in korean_numbers:
        return korean_numbers[text]

    # "스물하나", "스물두개" 같은 복합 표현 처리
    for key, value in sorted(korean_numbers.items(), key=lambda x: -len(x[0])):
        if text.startswith(key):
            remainder = text[len(key):]
            if remainder in korean_numbers:
                return value + korean_numbers[remainder]
            elif remainder.isdigit():
                return value + int(remainder)

    # 변환 실패시 None 반환
    return None


def parse_korean_time(time_text: str) -> str:
    """Convert time expressions to HH:MM:SS format (always PM for orders).
    Examples:
    - '6시' -> '18:00:00'
    - '6시 30분' -> '18:30:00'
    """
    time_text = time_text.strip()

    # "6시", "6시 30분" 형식 처리
    time_match = re.search(r'(\d+)\s*시(?:\s*(\d+)\s*분)?', time_text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0

        # 주문 시간은 항상 오후로 처리 (12시 미만이면 +12)
        if hour < 12:
            hour += 12

        return f"{hour:02d}:{minute:02d}:00"

    # 변환 실패시 원본 반환
    return time_text


def parse_korean_date(date_text: str) -> str:
    """Convert Korean date expressions to yyyy-mm-dd format (KST timezone)."""
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst)
    date_text = date_text.strip()

    # "오늘"
    if "오늘" in date_text:
        return today.strftime("%Y-%m-%d")

    # "내일"
    if "내일" in date_text:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # "모레"
    if "모레" in date_text:
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")

    # "이번 주 X요일" or "이번주 X요일"
    this_week_match = re.search(r'이번\s*주\s*([월화수목금토일])요일', date_text)
    if this_week_match:
        weekday_kr = this_week_match.group(1)
        weekday_map = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}
        target_weekday = weekday_map[weekday_kr]
        current_weekday = today.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:  # 이미 지났으면 다음 주
            days_ahead += 7
        target_date = today + timedelta(days=days_ahead)
        return target_date.strftime("%Y-%m-%d")

    # "다음 주 X요일" or "다음주 X요일"
    next_week_match = re.search(r'다음\s*주\s*([월화수목금토일])요일', date_text)
    if next_week_match:
        weekday_kr = next_week_match.group(1)
        weekday_map = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}
        target_weekday = weekday_map[weekday_kr]
        current_weekday = today.weekday()
        days_ahead = target_weekday - current_weekday + 7
        target_date = today + timedelta(days=days_ahead)
        return target_date.strftime("%Y-%m-%d")

    # "X월 Y일" 형식
    date_match = re.search(r'(\d+)월\s*(\d+)일', date_text)
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        year = today.year
        # 만약 입력된 월/일이 이미 지났으면 내년으로 설정
        try:
            target_date = datetime(year, month, day)
            if target_date < today:
                target_date = datetime(year + 1, month, day)
            return target_date.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # 변환 불가능한 경우 원본 반환
    return date_text


class ActionRecommendMenu(Action):
    def name(self) -> Text:
        return "action_menu_recommendation"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        occasion = tracker.get_slot("occasion")

        menus = {
            "valentine": {
                "name": "발렌타인 디너",
                "desc": "연인을 위한 낭만적인 코스입니다."
            },
            "french": {
                "name": "프렌치 디너",
                "desc": "격식 있는 가족 모임, 우아한 축하 자리에 어울리는 코스입니다."
            },
            "english": {
                "name": "잉글리시 디너",
                "desc": "브런치 스타일의 든든한 한 끼입니다."
            },
            "champagne": {
                "name": "샴페인 축제 디너",
                "desc": "생일이나 파티에 최적인 샴페인 포함 코스입니다."
            }
        }

        # 추천 메뉴 결정
        recommendations = []

        if occasion:
            occasion_lower = occasion.lower()

            # 생일/생신 관련
            if any(keyword in occasion_lower for keyword in ["생일", "생신", "가족"]):
                recommendations.append(menus["french"])
                recommendations.append(menus["champagne"])

            # 커플/발렌타인 관련
            elif any(keyword in occasion_lower for keyword in ["커플", "연인", "여자친구", "남자친구", "애인", "발렌타인", "데이트", "기념일"]):
                recommendations.append(menus["valentine"])

            # 브런치/혼자
            elif any(keyword in occasion_lower for keyword in ["브런치", "혼자"]):
                recommendations.append(menus["english"])

            # 파티/축하
            elif any(keyword in occasion_lower for keyword in ["파티", "축하"]):
                recommendations.append(menus["champagne"])

            # 기본 추천
            else:
                recommendations.append(menus["french"])

        # 메시지 생성
        if recommendations:
            if len(recommendations) == 1:
                message = f"{recommendations[0]['name']}를 추천드려요! {recommendations[0]['desc']}"
            else:
                menu_names = " 또는 ".join([r['name'] for r in recommendations])
                message = f"정말 축하드려요!🎉 {menu_names}는 어떠세요?"

            dispatcher.utter_message(text=message)
        else:
            dispatcher.utter_message(text="어떤 상황인지 다시 알려주시면 메뉴를 추천해 드릴게요!")

        return []


class ValidateOrderForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_order_form"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        """A list of required slots that the form has to fill."""
        # Return slots in the exact order they should be asked
        return [
            "menu_name",
            "menu_quantity",
            "serving_style",
            "side_menu_choice",
            "delivery_date",
            "delivery_time",
            "order_confirmation"
        ]

    def validate_menu_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate menu_name value."""
        valid_menus = ["발렌타인 디너", "프렌치 디너", "잉글리시 디너", "샴페인 축제 디너"]

        if slot_value and any(menu in slot_value for menu in valid_menus):
            return {"menu_name": slot_value}
        else:
            dispatcher.utter_message(text="죄송합니다. 유효한 메뉴를 선택해주세요.")
            return {"menu_name": None}

    def validate_menu_quantity(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate menu_quantity value."""
        # Extract menu_quantity entity from the message
        entities = tracker.latest_message.get('entities', [])
        quantity_value = None

        for entity in entities:
            if entity['entity'] == 'menu_quantity':
                quantity_value = entity['value']
                break

        # If no entity found, try to extract from full text
        if quantity_value is None:
            text = tracker.latest_message.get('text', '')
            # Try to find Korean numbers in the text
            korean_numbers = ['하나', '한', '둘', '두', '셋', '세', '넷', '네',
                            '다섯', '여섯', '일곱', '여덟', '아홉', '열']
            for korean_num in korean_numbers:
                if korean_num in text:
                    quantity_value = korean_num
                    break

            # If still no match, try to find digits
            if quantity_value is None:
                import re
                digit_match = re.search(r'\d+', text)
                if digit_match:
                    quantity_value = digit_match.group()

        if quantity_value is None:
            dispatcher.utter_message(text="올바른 수량을 입력해주세요. (예: 2개, 두 개)")
            return {"menu_quantity": None}

        # Try to convert Korean number to int
        quantity = korean_number_to_int(quantity_value)

        # If conversion failed, try direct int conversion
        if quantity is None:
            try:
                quantity = int(quantity_value)
            except (ValueError, TypeError):
                dispatcher.utter_message(text="올바른 수량을 입력해주세요. (예: 2개, 두 개)")
                return {"menu_quantity": None}

        # Validate range
        if quantity > 0 and quantity <= 100:
            return {"menu_quantity": str(quantity)}
        else:
            dispatcher.utter_message(text="수량은 1개에서 100개 사이로 주문해주세요.")
            return {"menu_quantity": None}

    def validate_serving_style(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate serving_style value."""
        valid_styles = ["심플 스타일", "디럭스 스타일", "그랜드 스타일"]

        if slot_value and any(style in slot_value for style in valid_styles):
            return {"serving_style": slot_value}
        else:
            dispatcher.utter_message(text="서빙 스타일을 다시 선택해주세요. (심플/디럭스/그랜드)")
            return {"serving_style": None}

    def validate_side_menu_choice(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate side menu choice and extract side items if selected."""
        # Get the latest user message and entities
        latest_intent = tracker.latest_message.get('intent', {}).get('name')

        # Check if user wants to add side menu
        if latest_intent == 'select_side_menu':
            # Extract side menu entities from the message
            side_names = tracker.latest_message.get('entities', [])
            side_name_list = [e['value'] for e in side_names if e['entity'] == 'side_name']
            side_quantity_raw = [e['value'] for e in side_names if e['entity'] == 'side_quantity']

            # If no entities found, try to extract from text
            if not side_quantity_raw:
                text = tracker.latest_message.get('text', '')
                korean_numbers = ['하나', '한', '둘', '두', '셋', '세', '넷', '네',
                                '다섯', '여섯', '일곱', '여덟', '아홉', '열']
                import re
                # Find all numbers (Korean and digits) in text
                for korean_num in korean_numbers:
                    if korean_num in text:
                        side_quantity_raw.append(korean_num)
                # Also find digits
                digit_matches = re.findall(r'\d+', text)
                side_quantity_raw.extend(digit_matches)

            # Convert all Korean numbers to integers
            side_quantity_list = []
            for qty in side_quantity_raw:
                converted = korean_number_to_int(qty)
                if converted is None:
                    try:
                        converted = int(qty)
                    except (ValueError, TypeError):
                        converted = None
                if converted is not None:
                    side_quantity_list.append(str(converted))

            if side_name_list and side_quantity_list:
                return {
                    "side_menu_choice": "yes",
                    "side_name": side_name_list,
                    "side_quantity": side_quantity_list
                }
            else:
                dispatcher.utter_message(text="사이드 메뉴와 수량을 함께 알려주세요. (예: 빵 두 개랑 샴페인 한 병)")
                return {"side_menu_choice": None}

        # Check if user doesn't want side menu
        elif latest_intent == 'deny' or any(keyword in slot_value.lower() for keyword in ["필요없", "안할", "괜찮"]):
            return {
                "side_menu_choice": "no",
                "side_name": None,
                "side_quantity": None
            }
        else:
            dispatcher.utter_message(text="사이드 메뉴를 추가하시겠어요?")
            return {"side_menu_choice": None}

    def validate_delivery_date(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate and convert delivery date to yyyy-mm-dd format."""
        # Extract date entity from the message
        entities = tracker.latest_message.get('entities', [])
        date_value = None
        time_value = None

        for entity in entities:
            if entity['entity'] == 'date':
                date_value = entity['value']
            elif entity['entity'] == 'time':
                time_value = entity['value']

        if date_value is None:
            dispatcher.utter_message(text="원하시는 배송 일시를 알려주세요!")
            return {"delivery_date": None}

        # Convert Korean date expression to yyyy-mm-dd
        standardized_date = parse_korean_date(date_value)

        if standardized_date is None:
            dispatcher.utter_message(text="올바른 날짜 형식을 입력해주세요. (예: 내일, 모레, 12월 8일)")
            return {"delivery_date": None}

        # Also set delivery_time if provided together and convert to HH:MM format
        result = {"delivery_date": standardized_date}
        if time_value:
            standardized_time = parse_korean_time(time_value)
            result["delivery_time"] = standardized_time

        return result

    def validate_delivery_time(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate and convert delivery time to HH:MM:SS format."""
        # Extract time entity from the message
        entities = tracker.latest_message.get('entities', [])
        time_value = None

        for entity in entities:
            if entity['entity'] == 'time':
                time_value = entity['value']
                break

        # If no entity found, try to extract from full text
        if time_value is None:
            text = tracker.latest_message.get('text', '')
            import re

            # Try to match numeric time pattern like "6시", "7시 30분"
            time_match = re.search(r'(\d+)\s*시(?:\s*(\d+)\s*분)?', text)
            if time_match:
                hour = time_match.group(1)
                minute = time_match.group(2) if time_match.group(2) else "00"
                time_value = f"{hour}시 {minute}분" if minute != "00" else f"{hour}시"
            else:
                # Try to match Korean number time pattern like "여섯 시", "일곱 시"
                korean_hour_pattern = r'(하나|한|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟|아홉|열|열하나|열한|열둘|열두)\s*시'
                korean_match = re.search(korean_hour_pattern, text)
                if korean_match:
                    korean_hour = korean_match.group(1)
                    # Convert Korean number to digit
                    hour_int = korean_number_to_int(korean_hour)
                    if hour_int:
                        time_value = f"{hour_int}시"

        if time_value is None:
            dispatcher.utter_message(text="올바른 시간을 입력해주세요. (예: 6시, 7시 30분)")
            return {"delivery_time": None}

        # Convert to standard HH:MM:SS format
        standardized_time = parse_korean_time(time_value)

        if standardized_time is None or standardized_time == time_value:
            dispatcher.utter_message(text="올바른 시간 형식을 입력해주세요. (예: 6시, 7시 30분)")
            return {"delivery_time": None}

        return {"delivery_time": standardized_time}

    def validate_order_confirmation(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate order confirmation."""
        latest_intent = tracker.latest_message.get('intent', {}).get('name')

        # 'deny'면 확인 완료
        if latest_intent == 'deny':
            return {"order_confirmation": True}
        # 'affirm'이면 추가 요청이 있다는 뜻이므로 다시 물어봄
        elif latest_intent == 'affirm':
            dispatcher.utter_message(text="추가로 필요하신 사항을 말씀해주세요.")
            return {"order_confirmation": None}
        else:
            # 명확하지 않으면 다시 물어봄
            return {"order_confirmation": None}


class ActionSubmitOrder(Action):
    def name(self) -> Text:
        return "action_submit_order"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        menu_name = tracker.get_slot("menu_name")
        menu_quantity = tracker.get_slot("menu_quantity")
        serving_style = tracker.get_slot("serving_style")
        side_name = tracker.get_slot("side_name")
        side_quantity = tracker.get_slot("side_quantity")
        delivery_date = tracker.get_slot("delivery_date")
        delivery_time = tracker.get_slot("delivery_time")

        # Build order summary message
        message = f"주문이 완료되었습니다!\n\n"
        message += f"📋 주문 내역\n"
        message += f"  📌 메뉴: {menu_name}\n"
        message += f"  📌 수량: {menu_quantity}개\n"
        message += f"  📌 서빙 스타일: {serving_style}\n"

        if side_name and side_quantity:
            message += f"\n🍽️ 사이드 메뉴\n"
            if isinstance(side_name, list) and isinstance(side_quantity, list):
                for name, qty in zip(side_name, side_quantity):
                    message += f"  📌 {name} {qty}개\n"
            else:
                message += f" 📌 {side_name} {side_quantity}개\n"

        message += f"\n📦 배송 정보\n"
        message += f"  📌 날짜: {delivery_date}\n"
        message += f"  📌 시간: {delivery_time}\n"
        message += f"\n감사합니다! 맛있게 드세요 😊"

        dispatcher.utter_message(
            text=message,
            json_message={
                "order_data": {
                    "menu_name": menu_name,
                    "menu_quantity": menu_quantity,
                    "serving_style": serving_style,
                    "side_name": side_name,
                    "side_quantity": side_quantity,
                    "delivery_date": delivery_date,
                    "delivery_time": delivery_time
                }
            }
        )

        # Reset slots
        return [
            SlotSet("menu_name", None),
            SlotSet("menu_quantity", None),
            SlotSet("serving_style", None),
            SlotSet("side_name", None),
            SlotSet("side_quantity", None),
            SlotSet("delivery_date", None),
            SlotSet("delivery_time", None)
        ]
