'''
NARRE
@author:
Chong Chen (cstchenc@163.com)

@ created:
27/8/2017
@references:

'''
import os
import numpy as np
import tensorflow as tf
import pickle
import datetime
import NARRE

import pickle
from tqdm import tqdm
from collections import defaultdict

def recall_at_k(rs, test_ur, k):
    assert k >= 1
    res = []
    for user in test_ur.keys():
        r = np.asarray(rs[user])[:k] != 0
        if r.size != k:
            raise ValueError('Relevance score length < k')
        if len(test_ur[user]) == 0:
            raise KeyError(f'Invalid User Index: {user}')
        res.append(sum(r) / len(test_ur[user]))

    return np.mean(res)

def dcg_at_k(r, k):
    '''
    Args:
        r: Relevance scores (list or numpy) in rank order
            (first element is the first item)
        k: Number of results to consider
    Returns:
        Discounted cumulative gain
    '''
    assert k >= 1
    r = np.asfarray(r)[:k] != 0
    if r.size:
        return np.sum(np.subtract(np.power(2, r), 1) / np.log2(np.arange(2, r.size + 2)))
    return 0.

def ndcg_at_k(r, k):
    '''
    Args:
        r: Relevance scores (list or numpy) in rank order
            (first element is the first item)
        k: Number of results to consider
    Returns:
        Normalized discounted cumulative gain
    '''
    assert k >= 1
    idcg = dcg_at_k(sorted(r, reverse=True), k)
    if not idcg:
        return 0.
    return dcg_at_k(r, k) / idcg

tf.flags.DEFINE_string("word2vec", None, "Word2vec file with pre-trained embeddings (default: None)") # ../data/google.bin
tf.flags.DEFINE_string("valid_data","../data/music/music.test", " Data for validation")
tf.flags.DEFINE_string("para_data", "../data/music/music.para", "Data parameters")
tf.flags.DEFINE_string("train_data", "../data/music/music.train", "Data for training")
# ==================================================

# Model Hyperparameters
# tf.flags.DEFINE_string("word2vec", "./data/rt-polaritydata/google.bin", "Word2vec file with pre-trained embeddings (default: None)")
tf.flags.DEFINE_integer("embedding_dim", 300, "Dimensionality of character embedding ")
tf.flags.DEFINE_string("filter_sizes", "3", "Comma-separated filter sizes ")
tf.flags.DEFINE_integer("num_filters", 100, "Number of filters per filter size")
tf.flags.DEFINE_float("dropout_keep_prob", 0.5, "Dropout keep probability ")
tf.flags.DEFINE_float("l2_reg_lambda", 0.001, "L2 regularizaion lambda")
# Training parameters
tf.flags.DEFINE_integer("batch_size", 50, "Batch Size ")
tf.flags.DEFINE_integer("num_epochs", 40, "Number of training epochs ")
# Misc Parameters
tf.flags.DEFINE_boolean("allow_soft_placement", True, "Allow device soft device placement")
tf.flags.DEFINE_boolean("log_device_placement", False, "Log placement of ops on devices")


def train_step(u_batch, i_batch, uid, iid, reuid, reiid, y_batch,batch_num):
    """
    A single training step
    """
    feed_dict = {
        deep.input_u: u_batch,
        deep.input_i: i_batch,
        deep.input_uid: uid,
        deep.input_iid: iid,
        deep.input_y: y_batch,
        deep.input_reuid: reuid,
        deep.input_reiid: reiid,
        deep.drop0: 0.8,

        deep.dropout_keep_prob: FLAGS.dropout_keep_prob
    }
    _, step, loss, accuracy, mae, u_a, i_a, fm = sess.run(
        [train_op, global_step, deep.loss, deep.accuracy, deep.mae, deep.u_a, deep.i_a, deep.score],
        feed_dict)
    time_str = datetime.datetime.now().isoformat()
    #print("{}: step {}, loss {:g}, rmse {:g},mae {:g}".format(time_str, batch_num, loss, accuracy, mae))
    return accuracy, mae, u_a, i_a, fm


def dev_step(u_batch, i_batch, uid, iid, reuid, reiid, y_batch, writer=None):
    """
    Evaluates model on a dev set

    """
    feed_dict = {
        deep.input_u: u_batch,
        deep.input_i: i_batch,
        deep.input_y: y_batch,
        deep.input_uid: uid,
        deep.input_iid: iid,
        deep.input_reuid: reuid,
        deep.input_reiid: reiid,
        deep.drop0: 1.0,
        deep.dropout_keep_prob: 1.0
    }
    step, loss, accuracy, mae = sess.run(
        [global_step, deep.loss, deep.accuracy, deep.mae],
        feed_dict)
    time_str = datetime.datetime.now().isoformat()
    # print("{}: step{}, loss {:g}, rmse {:g},mae {:g}".format(time_str, step, loss, accuracy, mae))

    return [loss, accuracy, mae]

if __name__ == '__main__':
    FLAGS = tf.flags.FLAGS
    # FLAGS._parse_flags()
    FLAGS.flag_values_dict()
    print("\nParameters:")
    for attr, value in sorted(FLAGS.__flags.items()):
        print("{}={}".format(attr.upper(), value))
    print("")

    print("Loading data...")
    pkl_file = open(FLAGS.para_data, 'rb')

    para = pickle.load(pkl_file)
    user_num = para['user_num']
    item_num = para['item_num']
    review_num_u = para['review_num_u']
    review_num_i = para['review_num_i']
    review_len_u = para['review_len_u']
    review_len_i = para['review_len_i']
    vocabulary_user = para['user_vocab']
    vocabulary_item = para['item_vocab']
    train_length = para['train_length']
    test_length = para['test_length']
    u_text = para['u_text']
    i_text = para['i_text']

    np.random.seed(2017)
    random_seed = 2017
    print(user_num)
    print(item_num)
    print(review_num_u)
    print(review_len_u)
    print(review_num_i)
    print(review_len_i)
    with tf.Graph().as_default():

        session_conf = tf.ConfigProto(allow_soft_placement=FLAGS.allow_soft_placement)
        session_conf.gpu_options.allow_growth = True
        sess = tf.Session(config=session_conf)
        with sess.as_default():
            deep = NARRE.NARRE(
                review_num_u=review_num_u,
                review_num_i=review_num_i,
                review_len_u=review_len_u,
                review_len_i=review_len_i,
                user_num=user_num,
                item_num=item_num,
                num_classes=1,
                user_vocab_size=len(vocabulary_user),
                item_vocab_size=len(vocabulary_item),
                embedding_size=FLAGS.embedding_dim,
                embedding_id=32,
                filter_sizes=list(map(int, FLAGS.filter_sizes.split(","))),
                num_filters=FLAGS.num_filters,
                l2_reg_lambda=FLAGS.l2_reg_lambda,
                attention_size=32,
                n_latent=32)
            tf.set_random_seed(random_seed)
            print(user_num)
            print(item_num)
            global_step = tf.Variable(0, name="global_step", trainable=False)

            # optimizer = tf.train.AdagradOptimizer(learning_rate=0.01, initial_accumulator_value=1e-8).minimize(deep.loss)
            optimizer = tf.train.AdamOptimizer(0.002, beta1=0.9, beta2=0.999, epsilon=1e-8).minimize(deep.loss)
            
            train_op = optimizer  # .apply_gradients(grads_and_vars, global_step=global_step)


            sess.run(tf.global_variables_initializer())

            saver = tf.train.Saver()

            if FLAGS.word2vec:
                # initial matrix with random uniform
                u = 0
                initW = np.random.uniform(-1.0, 1.0, (len(vocabulary_user), FLAGS.embedding_dim))
                # load any vectors from the word2vec
                print("Load word2vec u file {}\n".format(FLAGS.word2vec))
                with open(FLAGS.word2vec, "rb") as f:
                    header = f.readline()
                    vocab_size, layer1_size = map(int, header.split())
                    binary_len = np.dtype('float32').itemsize * layer1_size
                    for line in range(vocab_size):
                        word = []
                        while True:
                            ch = f.read(1)
                            if ch == ' ':
                                word = ''.join(word)
                                break
                            if ch != '\n':
                                word.append(ch)
                        idx = 0

                        if word in vocabulary_user:
                            u = u + 1
                            idx = vocabulary_user[word]
                            initW[idx] = np.fromstring(f.read(binary_len), dtype='float32')
                        else:
                            f.read(binary_len)
                sess.run(deep.W1.assign(initW))
                initW = np.random.uniform(-1.0, 1.0, (len(vocabulary_item), FLAGS.embedding_dim))
                # load any vectors from the word2vec
                print("Load word2vec i file {}\n".format(FLAGS.word2vec))

                item = 0
                with open(FLAGS.word2vec, "rb") as f:
                    header = f.readline()
                    vocab_size, layer1_size = map(int, header.split())
                    binary_len = np.dtype('float32').itemsize * layer1_size
                    for line in range(vocab_size):
                        word = []
                        while True:
                            ch = f.read(1)
                            if ch == ' ':
                                word = ''.join(word)
                                break
                            if ch != '\n':
                                word.append(ch)
                        idx = 0
                        if word in vocabulary_item:
                            item = item + 1
                            idx = vocabulary_item[word]
                            initW[idx] = np.fromstring(f.read(binary_len), dtype='float32')
                        else:
                            f.read(binary_len)

                sess.run(deep.W2.assign(initW))
                print(item)

            epoch = 1
            best_mae = 5
            best_rmse = 5
            train_mae = 0
            train_rmse = 0

            pkl_file = open(FLAGS.train_data, 'rb')

            train_data = pickle.load(pkl_file)

            train_data = np.array(train_data)
            pkl_file.close()

            pkl_file = open(FLAGS.valid_data, 'rb')

            test_data = pickle.load(pkl_file)
            test_data = np.array(test_data)
            pkl_file.close()

            data_size_train = len(train_data)
            data_size_test = len(test_data)
            batch_size = FLAGS.batch_size
            ll = int(len(train_data) / batch_size)

            ckpt_dirs = './ckpt/'
            if not os.path.exists(ckpt_dirs):
                os.makedirs(ckpt_dirs)

            for epoch in range(2):  # 40
                print(f'epoch {epoch} start......')
                # Shuffle the data at each epoch
                shuffle_indices = np.random.permutation(np.arange(data_size_train))
                shuffled_data = train_data[shuffle_indices]
                for batch_num in range(ll):

                    start_index = batch_num * batch_size
                    end_index = min((batch_num + 1) * batch_size, data_size_train)
                    data_train = shuffled_data[start_index:end_index]

                    uid, iid, reuid, reiid, y_batch = zip(*data_train)
                    u_batch = []
                    i_batch = []
                    for i in range(len(uid)):
                        u_batch.append(u_text[uid[i][0]])
                        i_batch.append(i_text[iid[i][0]])
                    u_batch = np.array(u_batch)
                    i_batch = np.array(i_batch)

                    t_rmse, t_mae, u_a, i_a, fm = train_step(u_batch, i_batch, uid, iid, reuid, reiid, y_batch,batch_num)
                    current_step = tf.train.global_step(sess, global_step)
                    train_rmse += t_rmse
                    train_mae += t_mae
                    if batch_num % 500 == 0 and batch_num > 1:
                        print("\nEvaluation:")
                        print(batch_num)

                        loss_s = 0
                        accuracy_s = 0
                        mae_s = 0

                        ll_test = int(len(test_data) / batch_size) + 1
                        for batch_num in range(ll_test):
                            start_index = batch_num * batch_size
                            end_index = min((batch_num + 1) * batch_size, data_size_test)
                            data_test = test_data[start_index:end_index]

                            userid_valid, itemid_valid, reuid, reiid, y_valid = zip(*data_test)
                            u_valid = []
                            i_valid = []
                            for i in range(len(userid_valid)):
                                u_valid.append(u_text[userid_valid[i][0]])
                                i_valid.append(i_text[itemid_valid[i][0]])
                            u_valid = np.array(u_valid)
                            i_valid = np.array(i_valid)

                            loss, accuracy, mae = dev_step(u_valid, i_valid, userid_valid, itemid_valid, reuid, reiid,
                                                           y_valid)
                            loss_s = loss_s + len(u_valid) * loss
                            accuracy_s = accuracy_s + len(u_valid) * np.square(accuracy)
                            mae_s = mae_s + len(u_valid) * mae
                        print ("loss_valid {:g}, rmse_valid {:g}, mae_valid {:g}".format(loss_s / test_length,
                                                                                         np.sqrt(
                                                                                             accuracy_s / test_length),
                                                                                         mae_s / test_length))
                        rmse = np.sqrt(accuracy_s / test_length)
                        mae = mae_s / test_length
                        if best_rmse > rmse:
                            best_rmse = rmse
                        if best_mae > mae:
                            best_mae = mae
                        print("")

                print(str(epoch) + ':\n')
                print("\nEvaluation:")
                print("train:rmse,mae:", train_rmse / ll, train_mae / ll)
                u_a = np.reshape(u_a[0], (1, -1))
                i_a = np.reshape(i_a[0], (1, -1))

                print(u_a)
                print(i_a)
                train_rmse = 0
                train_mae = 0

                loss_s = 0
                accuracy_s = 0
                mae_s = 0

                ll_test = int(len(test_data) / batch_size) + 1
                for batch_num in range(ll_test):
                    start_index = batch_num * batch_size
                    end_index = min((batch_num + 1) * batch_size, data_size_test)
                    data_test = test_data[start_index:end_index]

                    userid_valid, itemid_valid, reuid, reiid, y_valid = zip(*data_test)
                    u_valid = []
                    i_valid = []
                    for i in range(len(userid_valid)):
                        u_valid.append(u_text[userid_valid[i][0]])
                        i_valid.append(i_text[itemid_valid[i][0]])
                    u_valid = np.array(u_valid)
                    i_valid = np.array(i_valid)

                    loss, accuracy, mae = dev_step(u_valid, i_valid, userid_valid, itemid_valid, reuid, reiid, y_valid)
                    loss_s = loss_s + len(u_valid) * loss
                    accuracy_s = accuracy_s + len(u_valid) * np.square(accuracy)
                    mae_s = mae_s + len(u_valid) * mae
                print("loss_valid {:g}, rmse_valid {:g}, mae_valid {:g}".format(loss_s / test_length,
                                                                                np.sqrt(accuracy_s / test_length),
                                                                                mae_s / test_length))
                rmse = np.sqrt(accuracy_s / test_length)
                mae = mae_s / test_length
                if best_rmse > rmse:
                    best_rmse = rmse
                if best_mae > mae:
                    best_mae = mae
                print("")


                saver.save(sess, ckpt_dirs)
            print('best rmse:', best_rmse)
            print('best mae:', best_mae)


    print('end')


    # TODO 从这开始是新加的程序 和deepconn类似 
    def rank_step(u_batch, i_batch, uid, iid, reuid, reiid, y_batch, writer=None):
        feed_dict = {
            deep.input_u: u_batch,
            deep.input_i: i_batch,
            deep.input_y: y_batch,
            deep.input_uid: uid,
            deep.input_iid: iid,
            deep.input_reuid: reuid,
            deep.input_reiid: reiid,
            deep.drop0: 1.0,
            deep.dropout_keep_prob: 1.0
        }

        predictions = sess.run([deep.predictions], feed_dict)

        return predictions

    def get_ur(df):
        ur = defaultdict(set)
        for _, row in df.iterrows():
            ur[int(row['user'])].add(int(row['item']))

        return ur

    import pandas as pd
    test_df = pd.read_csv('../data/music/music_test.csv', header=None, names=['user', 'item', 'rating'])
    train_df = pd.read_csv('../data/music/music_train.csv', header=None, names=['user', 'item', 'rating'])
    valid_df = pd.read_csv('../data/music/music_valid.csv', header=None, names=['user', 'item', 'rating'])
    train_df = pd.concat([train_df, valid_df], ignore_index=True)
    test_ur = get_ur(test_df)
    total_train_ur = get_ur(train_df)
    item_pool = set(range(item_num))

    test_ucands = defaultdict(list)
    for k, v in test_ur.items():
        if k >= user_num:
            continue
        sub_item_pool = item_pool - total_train_ur[k] # remove GT & interacted
        test_ucands[k] = list(sub_item_pool)

    print('')
    print('Generate recommend list...')
    print('')
    preds = {}
    for u in tqdm(test_ucands.keys()):
        tmp = pd.DataFrame({'user': [u for _ in test_ucands[u]], 
                            'item': test_ucands[u], 
                            'rating': [0. for _ in test_ucands[u]], # fake label, make nonsense
                            })

        # TODO 这里要依照着pro_data做相同操作, 这里应该还有两列 reuid reiid
        data_rank = np.array(list(zip(tmp['user'].values[:, np.newaxis], 
                                      tmp['item'].values[:, np.newaxis], 
                                      tmp['rating'].values[:, np.newaxis])))

        userid_rank, itemid_rank, reuid_rank, reiid_rank, y_rank = zip(*data_rank)
        u_rank = []
        i_rank = []
        for i in range(len(userid_rank)):
            u_rank.append(u_text[userid_rank[i][0]])
            i_rank.append(i_text[itemid_rank[i][0]])
        u_rank = np.array(u_rank)
        u_rank = np.array(u_rank)
        predictions = rank_step(u_rank, i_rank, userid_rank, itemid_rank, reuid_rank, reiid_rank, y_rank)
        pred_rates = [rate[0] for rate in predictions[0]]
        rec_idx = np.argsort(pred_rates)[::-1][:50]
        top_n = np.array(test_ucands[u])[rec_idx]
    
        preds[u] = top_n

    for u in preds.keys():
        preds[u] = [1 if i in test_ur[u] else 0 for i in preds[u]]

    print('Save metric@k result to res folder...')
    result_save_path = f'./res/'
    if not os.path.exists(result_save_path):
        os.makedirs(result_save_path)

    res = pd.DataFrame({'metric@K': ['rec', 'ndcg']})
    for k in [1, 5, 10, 20, 30, 50]:
        tmp_preds = preds.copy()
        tmp_preds = {key: rank_list[:k] for key, rank_list in tmp_preds.items()}
        
        rec_k = recall_at_k(tmp_preds, test_ur, k)
        ndcg_k = np.mean([ndcg_at_k(r, k) for r in tmp_preds.values()])

        res[k] = np.array([rec_k, ndcg_k])

    res.to_csv(f'{result_save_path}topk_res.csv', index=False)
