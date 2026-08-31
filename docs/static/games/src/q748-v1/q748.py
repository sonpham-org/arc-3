"""q748 Breakwater Obligation -- a first creditor wakes after two solved harbor tasks."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,CHANNEL,IDENTITY,DEBT,REWARD,SUBGOAL,REPAY,BAD=15,8,11,6,2,9,4,13,14
LEVELS=[
 {"name":"Dormant Debt","plan":(1,4,4,5)},{"name":"Right Creditor","plan":(2,3,4,4,5)},
 {"name":"Identity Returns","plan":(1,3,4,4,3,5)},{"name":"Distracting Debt","plan":(1,2,4,4,5)},
 {"name":"Two Creditors","plan":(2,3,1,4,4,5,5)},{"name":"Breakwater Obligation","plan":(1,3,2,4,4,3,5,5)}]
def advance(s,a,x):
 slots,debts,seed,subgoals,affordance,reward,repaid=s;slots=list(slots);debts=list(debts);repaid=list(repaid)
 if a in (1,2):
  who=slots[a-1];debts[who]+=1;reward+=3
  if seed is None:seed=who
 elif a==3:slots.reverse()
 elif a==4:
  subgoals+=1
  if subgoals>=2:affordance=seed
 elif a==5:
  who=slots[0]
  if subgoals<2 or who!=affordance or debts[who]<=0:return None
  debts[who]-=1;reward-=1;repaid.append(who)
 return tuple(slots),tuple(debts),seed,subgoals,affordance,reward,tuple(repaid)
def target(x):
 s=((0,1),(0,0),None,0,None,0,())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HARBOR;f[9:35,8:29]=CHANNEL;f[9:35,35:56]=CHANNEL+1
  for pos,who in enumerate(g.slots):x=11+pos*27;f[14:25,x:x+15]=IDENTITY+who*3;f[29:32,x:x+g.debts[who]*7]=DEBT
  f[41:45,8:8+g.reward*4]=REWARD;f[48:51,8:8+g.subgoals*8]=SUBGOAL;f[53:56,8:8+len(g.repaid)*9]=REPAY
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q748(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q748",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots=(0,1);self.debts=(0,0);self.seed=None;self.subgoals=0;self.affordance=None;self.reward=0;self.repaid=()
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.slots,self.debts,self.seed,self.subgoals,self.affordance,self.reward,self.repaid),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.slots,self.debts,self.seed,self.subgoals,self.affordance,self.reward,self.repaid=s
  elif a==6:
   if (self.slots,self.debts,self.seed,self.subgoals,self.affordance,self.reward,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
