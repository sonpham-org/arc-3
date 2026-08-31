"""q743 Ember Obligation -- repay delayed debt by identity after vessel swaps."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,SLOT,IDENTITY,DEBT,REWARD,SWAP,RESOURCE,BAD=1,8,9,6,2,11,4,10,15
LEVELS=[
 {"name":"Borrow and Return","plan":(1,5),"budget":4},{"name":"Right-Hand Debt","plan":(2,3,5),"budget":5},
 {"name":"Identity Returns","plan":(1,3,3,5),"budget":6},{"name":"Distracting Reward","plan":(1,4,3,3,5),"budget":7},
 {"name":"Two Creditors","plan":(1,2,3,5,3,5),"budget":8},{"name":"Ember Obligation","plan":(1,3,2,4,3,5,5),"budget":9}]
def advance(s,a,x):
 slots,debts,reward,repaid,resource=s;slots=list(slots);debts=list(debts);repaid=list(repaid)
 if resource<=0:return None
 resource-=1
 if a==1:debts[slots[0]]+=1;reward+=3
 elif a==2:debts[slots[1]]+=1;reward+=3
 elif a==3:slots.reverse()
 elif a==4:reward+=1
 elif a==5:
  who=slots[0]
  if debts[who]<=0:return None
  debts[who]-=1;reward-=1;repaid.append(who)
 return tuple(slots),tuple(debts),reward,tuple(repaid),resource
def target(x):
 s=((0,1),(0,0),0,(),x["budget"])
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN;f[10:35,8:29]=SLOT;f[10:35,35:56]=SLOT
  for pos,who in enumerate(g.slots):
   x=11+pos*27;f[14:25,x:x+15]=IDENTITY+who*5;f[28:31,x:x+g.debts[who]*7]=DEBT
  f[40:44,8:8+g.reward*4]=REWARD;f[47:50,8:8+len(g.repaid)*8]=SWAP;f[53:57,8:8+g.resource*5]=RESOURCE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q743(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q743",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots=(0,1);self.debts=(0,0);self.reward=0;self.repaid=();self.resource=self.cfg["budget"]
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.slots,self.debts,self.reward,self.repaid,self.resource),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.slots,self.debts,self.reward,self.repaid,self.resource=s
  elif a==6:
   if (self.slots,self.debts,self.reward,self.repaid,self.resource)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
