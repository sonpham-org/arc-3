"""q750 Spore Obligation -- repay causal identity only at unequal-clock alignment."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,GLASS,IDENTITY,DEBT,REWARD,CLOCK,REPAY,BAD=9,12,11,6,2,4,8,13,15
LEVELS=[
 {"name":"Twin Creditors","cycles":(2,2),"swap":False},{"name":"Unequal Creditors","cycles":(2,3),"swap":False},
 {"name":"Swapped Identity","cycles":(3,3),"swap":True},{"name":"Sparse Repayment","cycles":(3,4),"swap":False},
 {"name":"Long Obligation","cycles":(4,5),"swap":True},{"name":"Spore Obligation","cycles":(5,6),"swap":True}]
for x in LEVELS:x["plan"]=(3,)*int(x["swap"])+(1,)*x["cycles"][0]+(2,)*x["cycles"][1]+(5,)
def advance(s,a,x):
 slots,debts,seed,clocks,reward,repaid=s;slots=list(slots);debts=list(debts);clocks=list(clocks);repaid=list(repaid)
 if a in (1,2):
  who=slots[a-1];debts[who]+=1;reward+=2
  if seed is None:seed=who
  clocks[a-1]=(clocks[a-1]+1)%x["cycles"][a-1]
 elif a==3:slots.reverse()
 elif a==4:clocks=[(clocks[i]+1)%x["cycles"][i] for i in range(2)]
 elif a==5:
  who=slots[0]
  if tuple(clocks)!=(0,0) or who!=seed or debts[who]<=0:return None
  debts[who]-=1;reward-=1;repaid.append(who)
 return tuple(slots),tuple(debts),seed,tuple(clocks),reward,tuple(repaid)
def target(x):
 s=((0,1),(0,0),None,(0,0),0,())
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GREENHOUSE;f[8:34,8:29]=GLASS;f[8:34,35:56]=GLASS+1
  for pos,who in enumerate(g.slots):x=11+pos*27;f[13:24,x:x+15]=IDENTITY+who*3;f[28:31,x:x+min(g.debts[who],6)*5]=DEBT
  f[37:39,8:56]=REWARD;f[40:44,8:8+g.reward*3]=REWARD;f[47:50,8:8+g.clocks[0]*8]=CLOCK;f[52:55,8:8+g.clocks[1]*7]=CLOCK+2
  if g.repaid:f[57:60,39:56]=REPAY
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q750(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q750",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.slots=(0,1);self.debts=(0,0);self.seed=None;self.clocks=(0,0);self.reward=0;self.repaid=()
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.slots,self.debts,self.seed,self.clocks,self.reward,self.repaid),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.slots,self.debts,self.seed,self.clocks,self.reward,self.repaid=s
  elif a==6:
   if (self.slots,self.debts,self.seed,self.clocks,self.reward,self.repaid)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
