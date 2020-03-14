import re
import json
import io
import os

from fonetika.metaphone import RussianMetaphone
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from translit import detranslify
from pytils import numeral


class FuzzySearcher:
    def __init__(self):
        self.names = {}
        self.metaphone = RussianMetaphone(reduce_phonemes=True)
        pass

    def find(self, name, threshold=100, count=5, scorer="default"):
        t_name = self.transform_string(name)

        if scorer == "default":
            sc = fuzz.WRatio
        elif scorer == "simple":
            sc = fuzz.ratio
        elif scorer == "partial":
            sc = fuzz.partial_ratio
        elif scorer == "sort":
            sc = fuzz.token_sort_ratio
        elif scorer == "set":
            sc = fuzz.token_set_ratio

        found_names = process.extract(t_name, list(self.names.keys()), limit=count, scorer=sc)
        res_names = []
        for i in found_names:
            if i[1] >= threshold:
                res_names.append((self.names[i[0]], i[1]))
        return res_names

    @staticmethod
    def translit_string(string):
        eng = re.findall("[a-zA-Z]+", string)
        if not eng:
            return string
        ru = [detranslify(i) for i in eng]
        for i in range(len(eng)):
            string = string.replace(eng[i], ru[i])
        return string

    @staticmethod
    def conversion_num(string):
        num = re.findall("[0-9]+", string)
        if not num:
            return string
        conv_num = [numeral.in_words(float(i)) for i in num]
        for i in range(len(num)):
            string = string.replace(num[i], conv_num[i])
        return string

    @staticmethod
    def replace_size(string):
        sizes = re.findall("[0-9]+[.,]?[0-9]*[\s]*[сcmм]?[сcmм]?[\s]*[xх*][\s]*"
                           "[0-9]+[.,]?[0-9]*[\s]*[сcmм]?[сcmм]?[\s]*[xх*]*[\s]*"
                           "[0-9]+[.,]?[0-9]*[\s]*[сcmм]?[сcmм]?", string)
        mult = []
        for i in sizes:
            digits = re.findall("[0-9]+[.,]?[0-9]*", i)
            m = 1
            for j in digits:
                j = j.replace(",", ".")
                m *= float(j)
            if m.is_integer():
                m = int(m)
            else:
                m = round(m, 2)
            mult.append(m)
        for i in range(len(sizes)):
            string = string.replace(sizes[i], str(mult[i]))
        return string

    def transform_string(self, string):
        t_string = self.replace_size(string.lower())
        t_string = self.translit_string(t_string)
        t_string = self.conversion_num(t_string)
        t_string = self.metaphone.transform(t_string)
        return t_string

    def add_database(self, request):
        request = json.loads(request)
        _id = request["databaseId"]
        if self.check_cache(_id):
            self.load_cache(_id)
        for val in request["database"]:
            t_name = self.transform_string(val["name"])
            if self.names.get(t_name) is None:
                self.names.update(dict.fromkeys([t_name], [val]))
            else:
                self.names[t_name].append(val)
        self.save_cache(_id)
        return True

    def remove_database(self, request):
        request = json.loads(request)
        self.remove_cache(request["databaseId"])
        return True

    def find_in_database(self, request):
        request = json.loads(request)
        _id = request["databaseId"]
        res = {"databaseId": _id}
        tmp = []
        self.load_cache(_id)
        for val in request["search"]:
            found_res = self.find(val["name"], val["threshold"], val["count"], val["scorer"])
            temp = {"searchName": val["name"]}
            t = []
            for i in found_res:
                similarity = i[1]
                for j in i[0]:
                    t.append({"name": j["name"], "id": j["id"], "similarity": similarity})
            temp.update(dict.fromkeys(["results"], t))
            tmp.append(temp)
        res.update(dict.fromkeys(["response"], tmp))
        with io.open("response.json", "w", encoding="utf-8") as file:
            json.dump(res, file, indent=4, ensure_ascii=False)
        return res

    @staticmethod
    def remove_all_database():
        path = "Caches/"
        list_cashes = os.listdir(path)
        for i in list_cashes:
            os.remove(os.path.join(path, i))
        return True

    @staticmethod
    def check_cache(db_id):
        return os.path.exists(f"Caches/cache_{db_id}.json")

    def save_cache(self, db_id):
        if not os.path.exists("Caches"):
            os.makedirs("Caches")
        with io.open(f"Caches/cache_{db_id}.json", "w", encoding="utf-8") as file:
            json.dump(self.names, file, indent=4, ensure_ascii=False)

    def load_cache(self, db_id):
        if self.check_cache(db_id):
            with io.open(f"Caches/cache_{db_id}.json", "r", encoding="utf-8") as file:
                self.names = json.load(file)
        else:
            raise Exception("Сache not found.")

    def remove_cache(self, db_id):
        if self.check_cache(db_id):
            os.remove(f"Caches/cache_{db_id}.json")

