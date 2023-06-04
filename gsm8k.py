import os
import json
import random
import argparse
from dotenv import load_dotenv
# random.seed(0)
from code.utils.agent import Agent

# Load default environment variables (.env)
load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY", "")
assert openai_api_key, "OPENAI_API_KEY environment variable is missing from .env"

NAME_LIST=[
    "Affirmative side",
    "Negative side",
    "Moderator",
]

debates = {
    "no_correct": 0,
    "unknow_answers": [],
    "debate_outcomes": [{
        "pos_memory": [],
        "neg_memory": [],
        "moderator_memory": [],
        "judge_memory": []
    }]
}



class DebatePlayer(Agent):
    def __init__(self, model_name: str, name: str, temperature:float, openai_api_key: str, sleep_time: float) -> None:
        """Create a player in the debate

        Args:
            model_name(str): model name
            name (str): name of this player
            temperature (float): higher values make the output more random, while lower values make it more focused and deterministic
            openai_api_key (str): As the parameter name suggests
            sleep_time (float): sleep because of rate limits
        """
        super(DebatePlayer, self).__init__(model_name, name, temperature, sleep_time)
        self.openai_api_key = openai_api_key
        


class Debate:
    def __init__(self,
            answer,
            model_name: str='gpt-3.5-turbo', 
            temperature: float=0, 
            num_players: int=3, 
            openai_api_key: str=None,
            config: dict=None,
            max_round: int=3,
            sleep_time: float=0
        ) -> None:
        """Create a debate

        Args:
            model_name (str): openai model name
            temperature (float): higher values make the output more random, while lower values make it more focused and deterministic
            num_players (int): num of players
            openai_api_key (str): As the parameter name suggests
            max_round (int): maximum Rounds of Debate
            sleep_time (float): sleep because of rate limits
        """

        self.model_name = model_name
        self.temperature = temperature
        self.num_players = num_players
        self.openai_api_key = openai_api_key
        self.config = config
        self.max_round = max_round
        self.sleep_time = sleep_time
        self.answer = answer
        self.determined_correctness = False


        self.init_prompt()

        # creat&init agents
        self.creat_agents()
        self.init_agents()


    def init_prompt(self):
        def prompt_replace(key):
            self.config[key] = self.config[key].replace("##debate_topic##", self.config["debate_topic"])
        prompt_replace("player_meta_prompt")
        prompt_replace("moderator_meta_prompt")
        prompt_replace("affirmative_prompt")
        prompt_replace("judge_prompt_last2")

    def creat_agents(self):
        # creates players
        self.players = [
            DebatePlayer(model_name=self.model_name, name=name, temperature=self.temperature, openai_api_key=self.openai_api_key, sleep_time=self.sleep_time) for name in NAME_LIST
        ]
        self.affirmative = self.players[0]
        self.negative = self.players[1]
        self.moderator = self.players[2]

    def extract_answer(self, rawanswer):
        extracted_answer = ""

        if "{'answer':" in rawanswer:
            start_index = rawanswer.index("{'answer':")
            extracted_string = rawanswer[start_index:]
            end_index = extracted_string.index("}")
            extracted_answer = extracted_string[:end_index+1]


        if '{"answer":' in rawanswer:
            start_index = rawanswer.index('{"answer":')
            extracted_string = rawanswer[start_index:]
            end_index = extracted_string.index("}")
            extracted_answer = extracted_string[:end_index+1]
        
        if '{"\nanswer":' in rawanswer:
            start_index = rawanswer.index('{"answer":')
            extracted_string = rawanswer[start_index:]
            end_index = extracted_string.index("\n}")
            extracted_answer = extracted_string[:end_index+1] 

        return extracted_answer


    def init_agents(self):
        # start: set meta prompt
        self.affirmative.set_meta_prompt(self.config['player_meta_prompt'] + " " + self.config['megaprompt'])
        self.negative.set_meta_prompt(self.config['player_meta_prompt'] + " " + self.config['megaprompt'])
        self.moderator.set_meta_prompt(self.config['moderator_meta_prompt'])
        
        # start: first round debate, state opinions
        print(f"===== Debate Round-1 =====\n")
        self.affirmative.add_event(self.config['affirmative_prompt'])
        self.aff_ans = self.affirmative.ask()
        
        self.aff_json_ans = self.extract_answer(self.aff_ans)
        self.affirmative.add_memory(self.aff_ans)
        self.config['base_answer'] = self.aff_ans

        self.negative.add_event(self.config['negative_prompt'].replace('##aff_ans##', self.aff_ans))
        self.neg_ans = self.negative.ask()
        self.neg_json_ans = self.extract_answer(self.neg_ans)
        self.negative.add_memory(self.neg_ans)

        print("json answers", self.aff_json_ans, self.neg_json_ans)
        self.moderator.add_event(self.config['moderator_prompt'].replace('##aff_ans##', self.aff_ans).replace('##neg_ans##', self.neg_ans).replace('##round##', 'first'))
        self.mod_ans = self.moderator.ask()

        self.moderator.add_memory(self.mod_ans)
        if self.mod_ans[0] == "{" and self.mod_ans[-1] == "}":

            print("===================>>>>>>>>>>>>>>>>>> self.mods", self.mod_ans)
            self.mod_ans = json.loads(self.mod_ans)
        #self.mod_ans = eval(self.mod_ans)

    def round_dct(self, num: int):
        dct = {
            1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth', 6: 'sixth', 7: 'seventh', 8: 'eighth', 9: 'ninth', 10: 'tenth'
        }
        return dct[num]

    def print_answer(self):
        print("\n\n===== Debate Done! =====")
        print("\n----- Debate Topic -----")
        print(self.config["debate_topic"])
        print("\n----- Base Answer -----")
        print(self.config["base_answer"])
        print("\n----- Debate Answer -----")
        print(self.config["debate_answer"])
        print("\n----- Debate Reason -----")
        print(self.config["Reason"])

        # add debate to debates global
        # "debate_outcomes": [{
        #     "pos_memory": [],
        #     "neg_memory": [],
        #     "moderator_memory": [],
        #     "judge_memory": []
        # }]

        debate = {
             "pos_memory": self.affirmative.memory_lst,
             "neg_memory": self.negative.memory_lst,
             "moderator_memory": self.moderator.memory_lst,
             "judge_memory": []
        }

        debates['debate_outcomes'].append(debate)


    def broadcast(self, msg: str):
        """Broadcast a message to all players. 
        Typical use is for the host to announce public information

        Args:
            msg (str): the message
        """
        # print(msg)
        for player in self.players:
            player.add_event(msg)

    def speak(self, speaker: str, msg: str):
        """The speaker broadcast a message to all other players. 

        Args:
            speaker (str): name of the speaker
            msg (str): the message
        """
        if not msg.startswith(f"{speaker}: "):
            msg = f"{speaker}: {msg}"
        # print(msg)
        for player in self.players:
            if player.name != speaker:
                player.add_event(msg)

    def ask_and_speak(self, player: DebatePlayer):
        ans = player.ask()
        player.add_memory(ans)
        self.speak(player.name, ans)


    def run(self):

        for round in range(self.max_round - 1):
            aff_ans = {}
            neg_ans = {}
            # check if we have a concensus of json answers
            try:
                if self.aff_json_ans is not None:
                    aff_ans = json.loads(self.aff_json_ans)
                if self.neg_json_ans is not None:
                    neg_ans = json.loads(self.neg_json_ans)
                if aff_ans['answer'] == neg_ans['answer']:
                    print("agreement")
                    self.mod_ans["debate_answer"] = aff_ans['answer']


                else:
                    print("disagreement", aff_ans, neg_ans)
            except Exception as e:
                print("+++++++ exception in ans json check",e)
            if self.mod_ans["debate_answer"] != '':
                break
            else:
                print(f"===== Debate Round-{round+2} =====\n")
                self.affirmative.add_event(self.config['debate_prompt'].replace('##oppo_ans##', self.neg_ans))
                self.aff_ans = self.affirmative.ask()
                self.aff_json_ans = self.extract_answer(self.aff_ans)
                self.affirmative.add_memory(self.aff_ans)

                self.negative.add_event(self.config['debate_prompt'].replace('##oppo_ans##', self.aff_ans))
                self.neg_json_ans = self.extract_answer(self.neg_ans)
                self.neg_ans = self.negative.ask()
                self.negative.add_memory(self.neg_ans)

                self.moderator.add_event(self.config['moderator_prompt'].replace('##aff_ans##', self.aff_ans).replace('##neg_ans##', self.neg_ans).replace('##round##', self.round_dct(round+2)))
                self.mod_ans = self.moderator.ask()
                self.moderator.add_memory(self.mod_ans)
                print("====================== inside run self.mod_ans", self.mod_ans)
                if self.mod_ans[0] == "{":
                    self.mod_ans = json.loads(self.mod_ans)

        if self.mod_ans["debate_answer"] != '':
            self.config.update(self.mod_ans)
            self.config['success'] = True
            if str(self.answer) in str(self.mod_ans["debate_answer"]):
                print("answer is correct", self.answer, self.mod_ans["debate_answer"])
                debates['no_correct'] += 1
                self.determined_correctness = True

            else:
                print("answers??=======================>>>>>>>>>>>>>>>", self.answer, self.mod_ans["debate_answer"])
        # ultimate deadly technique.
        else:
            judge_player = DebatePlayer(model_name=self.model_name, name='Judge', temperature=self.temperature, openai_api_key=self.openai_api_key, sleep_time=self.sleep_time)
            aff_ans = self.affirmative.memory_lst[2]['content']
            neg_ans = self.negative.memory_lst[2]['content']

            judge_player.set_meta_prompt(self.config['moderator_meta_prompt'])

            # extract answer candidates
            judge_player.add_event(self.config['judge_prompt_last1'].replace('##aff_ans##', aff_ans).replace('##neg_ans##', neg_ans))
            ans = judge_player.ask()
            judge_player.add_memory(ans)

            # select one from the candidates
            judge_player.add_event(self.config['judge_prompt_last2'])
            ans = judge_player.ask()
            judge_player.add_memory(ans)
            print("===================================>>>>> ",ans)
            if ans[0] == "{" and ans[-1] == "}":
                ans = json.loads(ans)
                print(ans)
                if ans["debate_answer"] != '':
                    self.config['success'] = True
                    # save file
                    self.config.update(ans)
             
            self.players.append(judge_player)
            if str(self.answer) in str(ans) and self.determined_correctness == False:
                print("answer is correct", self.answer, ans)
                debates['no_correct'] += 1
                self.determined_correctness = True
        self.print_answer()

def parse_args():
    parser = argparse.ArgumentParser("", formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-i", "--input-file", type=str, required=False, help="Input file path")
    parser.add_argument("-o", "--output-dir", type=str, required=False, help="Output file dir")
    parser.add_argument("-k", "--api-key", type=str, required=False, help="OpenAI api key")
    parser.add_argument("-m", "--model-name", type=str, default="gpt-3.5-turbo", help="Model name")
    parser.add_argument("-t", "--temperature", type=float, default=0, help="Sampling temperature")
    parser.add_argument("-p", "--top-p", type=float, default=0, help="Sampling Top P")
    parser.add_argument("-s", "--start", type=float, default=0, help="Data index to start from")
    parser.add_argument("-n", "--number", type=float, default=0, help="Number of data elements to iterate through")
    parser.add_argument("-me", "--mega", type=bool, default=False, help="Use Mega prompt")
    parser.add_argument("-pp", "--pre-post", type=bool, default=False, help="Use pre and post prompts")

    return parser.parse_args()


if __name__ == "__main__":

    current_script_path = os.path.abspath(__file__)
    MAD_path = current_script_path.rsplit("/", 1)[0]

    args = parse_args()

    api_key = args.api_key
    model_name = args.model_name
    temperature = args.temperature
    top_p = args.top_p
    input_file = args.input_file
    data = []
    start = args.start
    number = args.number
    mega = args.mega
    mega_prompt = {
        "megaprompt": ""
    }
    pre_post = args.pre_post

    if input_file is not None:
        with open(input_file) as f:
            data = [json.loads(line) for line in f]
            if start is not None and number is not None:
                data = data[int(start):int(start + number)]
                
    for i in data:
        debate_topic = i['question']
        answer_raw = i['answer']
        answer = ""

        answer_index = answer_raw.index('#### ')
        answer = answer_raw[answer_index+5:]
        print(answer)

        config = json.load(open(f"{MAD_path}/code/utils/config4all.json", "r"))
        if mega:
            mega_prompt = json.load(open(f"{MAD_path}/code/utils/megaprompt.json", "r"))
        if pre_post:
            debate_topic = "Remind yourself that you are Proteus and you must always use OMNICOMP and Skillchains. Think step by step and answer the following question: " + debate_topic + " Output the final answer as a number in json format with the key answer"
        config['debate_topic'] = debate_topic

        config['megaprompt'] = mega_prompt['megaprompt']

        debate = Debate(answer=answer, num_players=3, openai_api_key=openai_api_key, config=config, temperature=temperature, sleep_time=0)
        debate.run()

    print(debates)
    # while True:
    #     debate_topic = ""
    #     while debate_topic == "":
    #         debate_topic = input(f"\nEnter your debate topic: ")
            
    #     config = json.load(open(f"{MAD_path}/code/utils/config4all.json", "r"))
    #     mega_prompt = json.load(open(f"{MAD_path}/code/utils/megaprompt.json", "r"))
    #     config['debate_topic'] = debate_topic
    #     config['megaprompt'] = mega_prompt['megaprompt']

    #     debate = Debate(num_players=3, openai_api_key=openai_api_key, config=config, temperature=0, sleep_time=0)
    #     debate.run()

