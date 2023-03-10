import torch
import torch.nn as nn
import torch.nn.functional as F


def _L2_loss_mean(x):
    return torch.mean(torch.sum(torch.pow(x, 2), dim=1, keepdim=False) / 2.)


class Embedding_based(nn.Module):

    def __init__(self, args, n_users, n_items, n_entities, n_relations):

        super(Embedding_based, self).__init__()
        self.use_pretrain = args.use_pretrain

        self.n_users = n_users
        self.n_items = n_items
        self.n_entities = n_entities
        self.n_relations = n_relations

        self.KG_embedding_type = args.KG_embedding_type

        self.embed_dim = args.embed_dim
        self.relation_dim = args.relation_dim

        self.cf_l2loss_lambda = args.cf_l2loss_lambda
        self.kg_l2loss_lambda = args.kg_l2loss_lambda

        self.user_embed = nn.Embedding(self.n_users, self.embed_dim)
        self.item_embed = nn.Embedding(self.n_items, self.embed_dim)
        nn.init.xavier_uniform_(self.user_embed.weight)
        nn.init.xavier_uniform_(self.item_embed.weight)

        self.entity_embed = nn.Embedding(self.n_entities, self.embed_dim)
        self.relation_embed = nn.Embedding(self.n_relations, self.relation_dim)
        nn.init.xavier_uniform_(self.entity_embed.weight)
        nn.init.xavier_uniform_(self.relation_embed.weight)

        # TransR 
        self.trans_M = nn.Parameter(torch.Tensor(self.n_relations, self.embed_dim, self.relation_dim))
        nn.init.xavier_uniform_(self.trans_M)


    def calc_kg_loss_TransR(self, h, r, pos_t, neg_t):
        """
        h:      (kg_batch_size)
        r:      (kg_batch_size)
        pos_t:  (kg_batch_size)
        neg_t:  (kg_batch_size)
        """
        r_embed = self.relation_embed(r)                                                # (kg_batch_size, relation_dim)
        W_r = self.trans_M[r]                                                           # (kg_batch_size, embed_dim, relation_dim)

        h_embed = self.entity_embed(h)                                                  # (kg_batch_size, embed_dim)
        pos_t_embed = self.entity_embed(pos_t)                                          # (kg_batch_size, embed_dim)
        neg_t_embed = self.entity_embed(neg_t)                                          # (kg_batch_size, embed_dim)

        # 1. ??????????????????????????????????????????????????????????????????????????????????????????
        r_mul_h = torch.matmul(h_embed, W_r)                                                                     # (kg_batch_size, relation_dim)
        r_mul_pos_t = torch.matmul(pos_t_embed, W_r)                                                                  # (kg_batch_size, relation_dim)
        r_mul_neg_t = torch.matmul(neg_t_embed, W_r)                                                                  # (kg_batch_size, relation_dim)

        # 2. ???????????????????????????????????????????????????????????????????????????????????????L2???????????????
        r_embed = torch.div(r_embed, torch.norm(r_embed, p=2, dim=-1, keepdim=True))
        r_mul_h = torch.div(r_mul_h, torch.norm(r_mul_h, p=2, dim=-1, keepdim=True))
        r_mul_pos_t = torch.div(r_mul_pos_t, torch.norm(r_mul_pos_t, p=2, dim=-1, keepdim=True))
        r_mul_neg_t = torch.div(r_mul_neg_t, torch.norm(r_mul_neg_t, p=2, dim=-1, keepdim=True))

        # 3. ?????????????????????????????? (h_embed, r_embed, pos_t_embed) ????????????????????? (h_embed, r_embed, neg_t_embed) ?????????
        pos_score = torch.sum(torch.mul(r_mul_h + r_embed - r_mul_pos_t, r_mul_h + r_embed - r_mul_pos_t), dim= -1, keepdim=False)                  # (kg_batch_size)
        neg_score = torch.sum(torch.mul(r_mul_h + r_embed - r_mul_neg_t, r_mul_h + r_embed - r_mul_neg_t), dim= -1, keepdim=False)                                                                    # (kg_batch_size)

        # 4. ?????? BPR Loss ?????????????????????????????????????????????????????????????????????
        kg_loss = (-1.0) * F.logsigmoid(neg_score - pos_score)
        kg_loss = torch.mean(kg_loss)

        l2_loss = _L2_loss_mean(r_mul_h) + _L2_loss_mean(r_embed) + _L2_loss_mean(r_mul_pos_t) + _L2_loss_mean(r_mul_neg_t)
        loss = kg_loss + self.kg_l2loss_lambda * l2_loss
        return loss


    def calc_kg_loss_TransE(self, h, r, pos_t, neg_t):
        """
        h:      (kg_batch_size)
        r:      (kg_batch_size)
        pos_t:  (kg_batch_size)
        neg_t:  (kg_batch_size)
        """
        r_embed = self.relation_embed(r)                                                # (kg_batch_size, relation_dim)
        
        h_embed = self.entity_embed(h)                                                  # (kg_batch_size, embed_dim)
        pos_t_embed = self.entity_embed(pos_t)                                          # (kg_batch_size, embed_dim)
        neg_t_embed = self.entity_embed(neg_t)                                          # (kg_batch_size, embed_dim)

        # 5. ???????????????????????????????????????????????????????????????????????????????????????L2???????????????
        r_embed = torch.div(r_embed, torch.norm(r_embed, p=2, dim=-1, keepdim= True))
        h_embed = torch.div(h_embed, torch.norm(h_embed, p=2, dim=-1, keepdim= True))
        pos_t_embed = torch.div(pos_t_embed, torch.norm(pos_t_embed, p=2, dim=-1, keepdim=True))
        neg_t_embed = torch.div(neg_t_embed, torch.norm(neg_t_embed, p=2, dim=-1, keepdim=True))

        # 6. ?????????????????????????????? (h_embed, r_embed, pos_t_embed) ????????????????????? (h_embed, r_embed, neg_t_embed) ?????????
        pos_score = torch.sum(torch.mul(h_embed+r_embed - pos_t_embed, h_embed+r_embed - pos_t_embed), dim= -1, keepdim=False)                                                                    # (kg_batch_size)
        neg_score = torch.sum(torch.mul(h_embed+r_embed - neg_t_embed, h_embed+r_embed - neg_t_embed), dim= -1, keepdim=False)                                                                  # (kg_batch_size)

        # 7. ?????? BPR Loss ?????????????????????????????????????????????????????????????????????
        kg_loss = (-1.0) *  torch.log(1e-10 + F.sigmoid(pos_score - neg_score))
        kg_loss = torch.mean(kg_loss)
        l2_loss = _L2_loss_mean(h_embed) + _L2_loss_mean(r_embed) + _L2_loss_mean(pos_t_embed) + _L2_loss_mean(neg_t_embed)
        loss = kg_loss + self.kg_l2loss_lambda * l2_loss
        return loss


    def calc_cf_loss(self, user_ids, item_pos_ids, item_neg_ids):
        """
        user_ids:       (cf_batch_size)
        item_pos_ids:   (cf_batch_size)
        item_neg_ids:   (cf_batch_size)
        """
        user_embed = self.user_embed(user_ids)                                          # (cf_batch_size, embed_dim)
        item_pos_embed = self.item_embed(item_pos_ids)                                  # (cf_batch_size, embed_dim)
        item_neg_embed = self.item_embed(item_neg_ids)                                  # (cf_batch_size, embed_dim)

        item_pos_kg_embed = self.entity_embed(item_pos_ids)                             # (cf_batch_size, embed_dim)
        item_neg_kg_embed = self.entity_embed(item_neg_ids)                             # (cf_batch_size, embed_dim)

        # 8. ??? ???????????? ?????? ???????????????????????????
        # ??????
        item_pos_cf_embed = item_pos_kg_embed + item_pos_embed  # (cf_batch_size, embed_dim)
        item_neg_cf_embed = item_neg_kg_embed + item_neg_embed  # (cf_batch_size, embed_dim)

        # # ??????
        # item_pos_cf_embed = torch.mul(item_pos_kg_embed,item_pos_embed)                                                            # (cf_batch_size, embed_dim)
        # item_neg_cf_embed = torch.mul(item_neg_kg_embed,item_neg_embed)                                                            # (cf_batch_size, embed_dim)

        # # ??????
        # item_pos_cf_embed = torch.concat([item_pos_kg_embed,item_pos_embed],dim=-1)                                                # (cf_batch_size, 2*embed_dim)
        # item_neg_cf_embed = torch.concat([item_neg_kg_embed,item_neg_embed],dim=-1)                                                # (cf_batch_size, 2*embed_dim)
        # user_embed = torch.concat([user_embed,user_embed],dim=-1)                                                                  # (cf_batch_size, 2*embed_dim)

        pos_score = torch.sum(user_embed * item_pos_cf_embed, dim=1)                    # (cf_batch_size)
        neg_score = torch.sum(user_embed * item_neg_cf_embed, dim=1)                    # (cf_batch_size)

        cf_loss = (-1.0) * torch.log(1e-10 + F.sigmoid(pos_score - neg_score))
        cf_loss = torch.mean(cf_loss)

        l2_loss = _L2_loss_mean(user_embed) + _L2_loss_mean(item_pos_cf_embed) + _L2_loss_mean(item_neg_cf_embed)
        loss = cf_loss + self.cf_l2loss_lambda * l2_loss
        return loss


    def calc_loss(self, user_ids, item_pos_ids, item_neg_ids, h, r, pos_t, neg_t):
        """
        user_ids:       (cf_batch_size)
        item_pos_ids:   (cf_batch_size)
        item_neg_ids:   (cf_batch_size)

        h:              (kg_batch_size)
        r:              (kg_batch_size)
        pos_t:          (kg_batch_size)
        neg_t:          (kg_batch_size)
        """
        if self.KG_embedding_type == 'TransR':
            calc_kg_loss = self.calc_kg_loss_TransR
        elif self.KG_embedding_type == 'TransE':
            calc_kg_loss = self.calc_kg_loss_TransE
        
        kg_loss = calc_kg_loss(h, r, pos_t, neg_t)
        cf_loss = self.calc_cf_loss(user_ids, item_pos_ids, item_neg_ids)
        
        loss = kg_loss + cf_loss
        return loss


    def calc_score(self, user_ids, item_ids):
        """
        user_ids:  (n_users)
        item_ids:  (n_items)
        """
        user_embed = self.user_embed(user_ids)                                          # (n_users, embed_dim)

        item_embed = self.item_embed(item_ids)                                          # (n_items, embed_dim)
        item_kg_embed = self.entity_embed(item_ids)                                     # (n_items, embed_dim)

        # 9. ??? ???????????? ?????? ???????????????????????????
        # ??????
        item_cf_embed = item_embed + item_kg_embed                                      # (n_items, embed_dim)
        # # ??????
        # item_cf_embed = torch.mul(item_embed, item_kg_embed)                                      # (n_items, embed_dim)
        # # ??????
        # item_cf_embed = torch.concat([item_embed ,item_kg_embed],dim=-1 )               # (n_items, 2*embed_dim)
        # user_embed = torch.concat([user_embed,user_embed],dim=-1 )  # (n_users, 2*embed_dim)


        cf_score = torch.matmul(user_embed, item_cf_embed.transpose(0, 1))              # (n_users, n_items)
        
        return cf_score


    def forward(self, *input, mode):
        if mode == 'train_cf&kg':
            return self.calc_loss(*input)
        if mode == 'train_cf':
            return self.calc_cf_loss(*input)
        if mode == 'TransR':
            return self.calc_kg_loss_TransR(*input)
        if mode == 'TransE':
            return self.calc_kg_loss_TransE(*input)
        else:
            return self.calc_score(*input)


