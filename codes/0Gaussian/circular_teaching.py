import torch
import torch.nn.functional as F 

import numpy as np

import math

def log10_scheduler(current_epoch, total_epoch, num_classes, lbd_last=0.5):
    
    init_thres = math.log(num_classes)
    last_thres = lbd_last

    # -log10(a*current_epoch+b)
    # current_epoch rangs from [1, total_epoch] <---- it's initial is 1, NOT 0.

    a = (math.pow(10,-init_thres) - math.pow(10,-last_thres)) / (1-total_epoch)
    b = math.pow(10,-init_thres) - a

    return - math.log(a * current_epoch + b, 10)

def ct_loss(all_logits_chunk, label, threshold=0.5):
    
    num_heads = len(all_logits_chunk)
    m = len(all_logits_chunk[0])

    ###########################################################################################################
    coeffs_spl = []
    with torch.no_grad():
        # -------- for each head, compute the avg. loss of m samplings
        avg_losses = []
        for head_idx, logits_chunk in enumerate(all_logits_chunk):
            avg_loss = .0
            for logits in logits_chunk:
                avg_loss += F.cross_entropy(logits, label, reduction='none')
            avg_loss = avg_loss / m
            avg_losses.append(avg_loss)
        # -------- circular-teaching among heads, self-paced learning
        for head_idx, avg_loss in enumerate(avg_losses):
            coeff_spl = avg_loss.lt(threshold).float()  # <-- easy samples with coeffs. 1
            hard_idx = avg_loss.gt(threshold)           # <-- hard samples
            coeff_spl[hard_idx] = (1+math.exp(-threshold))/(1+torch.exp(avg_losses[head_idx-num_heads+1][hard_idx]-threshold)) # <-- key codes
            coeffs_spl.append(coeff_spl)
    
    # -------- circular-teaching among heads, self-paced weighted sample loss
    losses = []
    for head_idx, logits_chunk in enumerate(all_logits_chunk):
        loss = sum([F.cross_entropy(logits, label, reduction='none') for logits in logits_chunk]) / m
        wloss = coeffs_spl[head_idx-1].squeeze() * loss # <-- key codes
        wloss = wloss.mean()
        losses.append(wloss)

    ###########################################################################################################
    ###########################################################################################################

    # -------- weighted head loss
    if num_heads > 1:
        loss_ce = sum(losses) / num_heads
    else:
        assert False, "number of heads should be greater than 1."

    return loss_ce, losses

    
    


