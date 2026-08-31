"""q746 Palimpsest Obligation -- a failed repayment reveals the causal identity."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,IDENTITY,DEBT,REWARD,FAIL,REPAY,BAD=5,8,11,6,2,9,15,4,13
LEVELS=[
 {"name":"Direct Repayment","plan":(1,5)},{"name":"Right Repayment","plan":(2,3,5)},
 {"name":"Visible Near Miss","plan":(1,3,4,3,5)},{"name":"Delayed Correction","plan":(1,3,4,3,3,3,5)},
 {"name":"Two Obligations","plan":(1,2,3,5,3,5)},{"name":"Palimpsest Obligation","plan":(1,3,4,2,3,5,5)}]
def advance(s,a,x):
 slots,debts,reward,failure,repaid=s;slots=list(slots);debts=list(debts);repaid=list(repaid)
 if a==1:debts[slots[0]]+=1;reward+=3
 elif a==2:debts[slots[1]]+=1;reward+=3
 elif a==3:slots.reverse()
 elif a==4:
  who=slots[0]
  if debts[who]>0:return None
  failure=(who,tuple(slots),tuple(debts))
 elif a==5:
  who=slots[0]
  if debts[who]<=0:return None
  debts[who]-=1;reward-=1;repaid.append(who)
 return tuple(slots),tuple(debts),reward,failure,tuple(repaid)
def target(x):
 s=((0,1),(0,0),0,None,())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE;f[9:35,8:29]=SHELF;f[9:35,35:56]=SHELF
  for pos,who in enumerate(g.slots):x=11+pos*27;f[14:25,x:x+15]=IDENTITY+who*3;f[29:32,x:x+g.debts[who]*7]=DEBT
  f[41:45,8:8+g.reward*4]=REWARD;f[48:51,8:8+len(g.repaid)*9]=REPAY
  if g.failure:f[53:57,8:30]=FAIL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q746(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q746",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots=(0,1);self.debts=(0,0);self.reward=0;self.failure=None;self.repaid=()
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.slots,self.debts,self.reward,self.failure,self.repaid),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.slots,self.debts,self.reward,self.failure,self.repaid=s
  elif a==6:
   if (self.slots,self.debts,self.reward,self.failure,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
