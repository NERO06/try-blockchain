#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
<ブロックチェーンを作ってみた>
・テキストメモでブロックチェーンについてはまとめている
<必要知識>
Pythonクラス(○)、 Flask library(○)、 ハッシュ関数(○)、 HTTPクライアント(○)
<全体の流れ>
ジェネシスブロックの生成(起点)
【1】トランザクションの処理フロー(②-1)
 ⑴.取引の実行
 ⑵.有効なトランザクションか確認
 　※ウォレット内の保有量の確認が必要。実際は、複数アドレスからの送信にも(ウォレットは複数アドレスを保存)対応できるようにする必要がある。
 ⑶.トランザクションリストの末尾に追加(①-3）

【2】マイニング(②–2）
　※ブロックチェーンの一番最初のブロックはマイニングとは別に作成される
 ⑴.以下の情報を取得し、ブロックを生成
  1.直前のブロック(ラストブロック)から生成したハッシュ値
  2.直近ブロックのプルーフ
 ⑵.プルーフオブワーク(①-4)
  1.ある定数のプルーフを含めたブロックを生成し、ハッシュ値を計算(①-5)
  2.ハッシュが条件(先頭4つが'0'など)に合うか照合(①-6)
  3.条件に合わなければプルーフを変更し、再度1から実行
  ※Qiitaのコードでは、直近ブロックのハッシュ値とプルーフに次コードのプルーフを取り込み、ハッシュ値を算出
   そのハッシュ値を算出し後に、ブロックを生成する流れを取っている
 ⑶.コインベースの実行
 ⑷.ブロックの生成(#①-7)

【3】コンセンサスアルゴリズム(②-3,①-8)
 ※全てのノードに対して行う
 ⑴.ノードからブロックチェーン情報を取得する
 ⑵.先頭のブロックから以下の確認を行う(①-9)
  1.自分よりもチェーンが長いか
　　➡︎長くない場合は次のノードへ
  2.1つ前のブロックから計算で算出したハッシュ値と現在ブロックに含まれているハッシュ値が等しいか
  3.ブロックに入っているプルーフを使って求めたハッシュ値が条件を満たすハッシュ値になっているか
  4.全てがYesの場合、自分のチェーンと置き換え

【別途】通信するノードを増やす(②-4)
 ⑴.POSTでノード情報を受け取る
 ⑵.URLを解析し、有効なURLか確認し、有効であれば、ノードに追加(①-10)
 <トランザクションイメージ>
 {
 "sender": "my address",                                                       #送り手(ウォレットアドレス)
 "recipient": "someone else's address",                                        #受け手（ウォレットアドレス）
 "amount": 5                                                                   #送金量
}
<ブロックイメージ>
block = {
    'index': 1,                                                                #1.インデックス
    'timestamp': 1506057125.900785,                                            #2.タイムスタンプ
    'transactions': [                                                          #3.トランザクション(複数入る)
        {
            'sender': "8527147fe1f5426f9dd545de4b27ee00",                      #3-1.送り手(ウォレットアドレス)
            'recipient': "a77f5cdfa2934df3954a5c7c7da5df1f",                   #3-2.受け手(ウォレットアドレス)
            'amount': 5,                                                       #3-3.送金量
        }
    ],
    'proof': 324984774000,                                                     #4.プルーフ
    'previous_hash': "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"     #5.1つ前のブロックのハッシュ値
}
    
<省略部分>
・プルーフの修正(Bitcoinでは、マイナーの増減に合わせトータルで10分となるよう条件が変更される)
・
"""

import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4
import requests
from flask import Flask, jsonify, request

#<①ブロックチェーンクラスの作成>
class Blockchain:
    #<基本設定>
    #①-1 コンストラクタ
    def __init__(self):
        self.current_transactions = []                                         #①-1-1<リスト> ブロックに格納されていないトランザクションリスト
        self.chain = []                                                        #①-1-2<リスト> ブロックチェーンを格納するリスト(個々のブロック自体は辞書型で格納される)
        self.nodes = set()                                                     #①-1-3<セット> ノードを格納(※ノードの重複が起きないようにset集合が使われている)
        self.new_block(previous_hash='1', proof=100)                           #①-1-4 ジェネシスブロック

    #①-2　ラストブロックリターン用クラス関数
    @property
    def last_block(self):
        """
        作業内容:直近のブロックを返す
        :return: <list>直近のブロック
        """
        return self.chain[-1]

    #<トランザクション用メソッド>
    #①-3　トランザクション追加用クラスメソッド
    def new_transaction(self, sender, recipient, amount):
        """
        作業内容:次のブロックに入るトランザクションの一覧を作成(トランザクションが実行されるごとに追加されていく)
        :param sender: <str>送り手のアドレス
        :param recipient: <str>受け手のアドレス
        :param amount: <int>送金量
        :return: <int>このトランザクションの塊を含むブロックのインデックス
        """
        self.current_transactions.append({                                     #トランザクションリストに辞書型で追加(①-1-1)
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    #<マイニング用メソッド>
    #①-4　プルーフオブワーク用クラス関数
    def proof_of_work(self, last_block):
        """
        作業内容:シンプルなプルーフオブワークアルゴリズム。条件を満たすプルーフを探す
        　　　　　※条件は①-6で指定
        ・具体的なフロー:⑴⑵⑶をそれぞれ求める
            　　　　   ➡︎⑴⑵⑶を結合しハッシュ値を求める(①-5で実行)
                   　 ➡︎ハッシュ値の最初の4つが0か確認する(①-6で実行)
                    　➡︎条件を満たすまで③のプルーフをなんども変更して再計算
                     ※⑴直前のブロックのプルーフ
                      ⑵直前のブロックのハッシュ値
                      ⑶今回のプルーフ
        :param last_block: <dict>last Block(from ②-2)
        :return: <int>proof
        """
        last_proof = last_block['proof']                                       #<int>⑴直前のブロックのプルーフ
        last_hash = self.hash(last_block)                                      #<str>⑵直前のハッシュ値の算出(①-5)

        proof = 0                                                              #<int>以下3段でプルーフを探索
        while self.valid_proof(last_proof, proof, last_hash) is False:         #①-6の戻り値がFalseの間実行し続ける
            proof += 1

        return proof

    #①-5　ハッシュ化用クラスメソッド
    @staticmethod
    def hash(block):
        """
        作業内容:ブロックのSHA-256ハッシュ値を作る
        :param block: <dict>ブロック(from ①-4)
        :return : <str>16進数のハッシュ値
        """

        block_string = json.dumps(block, sort_keys=True).encode()              #<byte>文字列のブロック➡︎Json文字列➡︎バイト型の流れで変換
                                                                               #※ソートすることでハッシュ値に一貫性を持たせる('sort_keys=True'辞書型データをキーでソート)
        return hashlib.sha256(block_string).hexdigest()

    #①-6　有効なプルーフを探すクラスメソッド
    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        """
        作業内容:条件を満たすハッシュ値を探す
        ・条件:ハッシュ値の最初の4つが0になる
        :param last_proof: <int>直前のブロックのプルーフ(from ①-4)
        :param proof: <int>プルーフ(from ①-4)
        :param last_hash: <str>直前のブロックのハッシュ値(from ①-4)
        :return: <bool>bool値を返す
        """
        guess = f'{last_proof}{proof}{last_hash}'.encode()                     #<byte>⑴⑵⑶を連結してbyte型に変更
        guess_hash = hashlib.sha256(guess).hexdigest()                         #<str>ハッシュ値の算出
        return guess_hash[:4] == "0000"

    #①-7 ブロック生成用クラス関数
    def new_block(self, proof, previous_hash):
        """
        作業内容:新しいブロックを作る
        :param proof: <int>プルーフオブワークの戻り値(from ②-2)
        :param previous_hash: <str>直前のブロックのハッシュ値(②-2)
        :return: <dict>新しいブロック
        """

        block = {                                                              #辞書型で記述
            'index': len(self.chain) + 1,                                      #ブロックチェーンの長さに1加える(新しいブロックのため)
            'timestamp': time(),                                               #タイムスタンプ
            'transactions': self.current_transactions,                         #ブロックに含むトランザクション情報の取得(from ①-1)
            'proof': proof,                                                    #プルーフ
            'previous_hash': previous_hash or self.hash(self.chain[-1]),       #直前のハッシュorハッシュ計算したものを代入(①-5)
        }

        self.current_transactions = []                                         #新しいブロック用のトランザクションを格納するためにリストを初期化(①-1-1)

        self.chain.append(block)                                               #ブロックチェーンの末尾に新しいブロックを追加(①-1-2)
        return block

    #<コンセンサスアルゴリズム用メソッド>
    #①–8　コンセンサスアルゴリズム
    def resolve_conflicts(self):
        """
        作業内容：他のノードからブロックチェーンをダウンロードし、長いものに置き換える
        :return: <bool>ブロックチェーンが置き換わったばいはTrue、そうでない場合はFalse
        """
        neighbours = self.nodes                                                #<セット>登録されたノードの情報を変数に格納(①-1-3)
        new_chain = None                                                       #<None>チェーン比較用の変数

        max_length = len(self.chain)                                           #<int>自身のブロックチェーンの長さを格納(①-1-2)

        for node in neighbours:                                                #登録されている全てのノードを順番に以下の命令を実行
            response = requests.get(f'http://{node}/chain')                    #<Response>比較するノードのブロックチェーン情報を取得
            
            if response.status_code == 200:                                    #情報が取得できた場合
                length = response.json()['length']                             #<int>比較ノードのlengthを格納
                chain = response.json()['chain']                               #<int>比較ノードのchainを格納

                if length > max_length and self.valid_chain(chain):            #長さを比較し、ブロックチェーンの有効性を確認(①-9)
                    max_length = length
                    new_chain = chain

        if new_chain:                                                          #'new_chain'(自分のとは異なる有効なブロックチェーンが存在する)に値があれば、それを自分のブロックチェーンと置き換え
            self.chain = new_chain
            return True

        return False                                                           #置き換えなかった場合は、Falseを返す

    #①-9 ブロックチェーンが正しいか確認するクラスメソッド
    def valid_chain(self, chain):
        """
        作業内容：ブロックチェーンが正しいか確認する
               ①ハッシュ②プルーフの2点
        :param chain: <dict>ブロックチェーン(from ①-4)※検証先のノードから持ってきたチェーン
        :return: <bool>有効ならTrue、無効ならFalse
        """
        last_block = chain[0]                                                  #<リスト>ブロックチェーンの1つ目から確認
        current_index = 1                                                      #<int>

        while current_index < len(chain):                                      #「インデックス番号=チェーンの長さ」となるまで下記実行文の繰り返し
            block = chain[current_index]                                       #<リスト>現在のブロック(last_blockはこの1つ目のブロック)
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")

            if block['previous_hash'] != self.hash(last_block):                #現在のブロックに格納されたハッシュ値(block['previous_hash'])と1つ前のブロックから求めたハッシュ値を照合
                return False                                                   #一致しない場合は、False(無効なブロックチェーン)を返す

            if not self.valid_proof(last_block['proof'], block['proof'],       #プルーフを再度照合(①-6)
                                    last_block['previous_hash']):              #※プルーフがわかっているため、プルーフオブワーク自体を行わなくて良い
                return False                                                   #プルーフが間違っているということは、改ざんが行われるなりしている無効なブロックチェーンということを意味する

            last_block = block                                                 #1つのブロックの照合が問題なく終わったら、次のブロックの照合へ進む
            current_index += 1
            
        return True                                                            #全部のブロックが有効ならTrueを返す

    #<ノードの登録用メソッド>
    #①-10　新しいノードの登録
    def register_node(self, address):
        """
        作業内容:ノードリストに新しいノードリストを登録する
        :param address: <str>ノードのアドレス(from ②-4)
                        例）'http://192.168.0.5:5000'
        :return : None
        """
        parsed_url = urlparse(address)                                         #<タプル>addressを解析➡
        if parsed_url.netloc:                                                  #netloc属性(ネットワークの位置を表す)に値が入る場合はnetloc属性値を追加
            self.nodes.add(parsed_url.netloc)                                  #①-1-3
        elif parsed_url.path:                                                  #netloc属性値には値が入らず、pathに値が入る場合('192.168.0.5:5000'など)はpath属性値を追加
            self.nodes.add(parsed_url.path)                                    #①-1-3
        else:                                                                  #それ以外の場合
            raise ValueError('Invalid URL')                                    #ValueErrorを返す



#ノードの作成
app = Flask(__name__)

#ノード独自の識別子を作る
node_identifier = str(uuid4()).replace('-', '')

#ブロックチェーンのインスタンス化➡︎コンストラクタの発動
blockchain = Blockchain()

#<②flaskのセットアップ>
#②-1 トランザクション用メソッド
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json(force=True)                                      #<Reponse>POSTされたトランザクションデータを解析し返す

    #POSTされたトランザクションが有効か確認
    required = ['sender', 'recipient', 'amount']                               #<リスト>トランザクションに必要な情報の定義
    if not all(k in values for k in required):                                 #トランザクションに必要な情報が入っているかの判定フロー
        return 'Missing values', 400                                           #満たしていない場合に実行し、ステータスコード400を返す

    index = blockchain.new_transaction(values['sender'],                       #<int>クラスメソッド(#①-3)の実行、戻り値（次のブロックのインデックス番号)を変数indexに格納
                                       values['recipient'], values['amount'])
    
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201

#②-2　マイニングアルゴリズム                                                         ※少し違ったマイニング手法を取っている
@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block                                         #<リスト>直前のブロック情報の取得(①-2)
    proof = blockchain.proof_of_work(last_block)                               #<int>プルーフオブワークの実行(①-4)

    blockchain.new_transaction(                                                #コインベースの実行(マイニング成功者への報酬)
        sender="0",                                                            #「sender=0」でコインベースからの報酬であることを表す
        recipient=node_identifier,                                             #受け手のアドレス
        amount=1,                                                              #報酬
    )

    previous_hash = blockchain.hash(last_block)                                #<str>直前のハッシュ値の計算(①-5)
    block = blockchain.new_block(proof, previous_hash)                         #<dict>新しいブロックの生成(①-7)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

#②-3　コンセンサス・アルゴリズム
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()                                  #コンセンサスアルゴリズムを実行(①-8)
    if replaced:                                                               #置き換えがあった場合(①-8がTrueを返す場合)
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:                                                                      #置き換えがなかった場合
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }
    return jsonify(response), 200

#②-4　ノード登録メソッド
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json(force=True)                                      #POSTされたJsonファイルを解析(mimeタイプで判断➡︎application/jsonかどうか)
    
    nodes = values.get('nodes')                                                #values➡︎Responseオブジェクト
    if nodes is None:                                                          #ノードがない場合
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:                                                         #ノードがある場合、ノードを登録
        blockchain.register_node(node)                                         #ノードに登録する(①-10)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

#②-5　全てのブロックチェーンを返すメソッド
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,                                             #ブロックチェーンの一覧(①-1-2)
        'length': len(blockchain.chain),                                       #ブロックチェーンの長さ(①-1-2)
    }
    return jsonify(response), 200

#②-6　起動用
if __name__ == '__main__':
    from argparse import ArgumentParser                                        #以下の5行でコマンドラインでノードを増やせるようにしている。
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port, debug=True)

"""
<関連知識>
・nnidモジュール
 固有の識別子であるUUIDを作るためのモジュール
・flask.jsonify
 MIMEタイプapplication/jsonのResponseオブジェクトに変換する
・flask.request.get_json()
 jsonファイルがPOSTされた場合にそれを解析し返す(jsonでない場合はNoneを返す)
 MIMEタイプで判断
 force引数…Trueの場合、MIMEタイプは無視される
・urllibパッケージ
 URLを扱う幾つかのモジュールを集めたパッケージ
・urllib.perseモジュール
 URLを解析して構成要素にするモジュール
・urllib.perse.urlperse()
 URLを解析し、6つの構成要素にし、6要素のタプルで返す。
 netloc属性を持ち、ネットワーク上での位置を表す(/以下のサーバー内のリソースの位置は格納されない)
 netloc属性に何も入らない場合は、空文字列を返す
・format文字列
 文字列前の「f」はformat文字列を表し、文字列内の{変数名}にはしてした変数の値が入る 
・requests.get()
 GETメソッドを送信し、レスポンスを返す
 requests.get().status_code…レスポンスのステータスコードを表す属性
・argparseモジュール
 コマンドライン引数の解析モジュール
 argparse.ArgumentParser()…AugumentParserオブジェクトを生成。コマンドラインで「--help」引数が使えるようになる
 ArgumentParserオブジェクト.add_argument(引数)…コマンドラインで引数を受け取って指定する。sys.argsのような機能。
                                           ArgumentParser.parse_args()が呼び出された時に実行される。
"""