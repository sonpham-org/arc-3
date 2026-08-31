"""q700 Vault Evidence -- move two conserved sample types until the decision margin is safe."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,SAMPLE1,SAMPLE2,SAMPLE3,A_ECHO,B_ECHO,STOP,BAD=6,11,9,14,10,12,8,13,15
LEVELS=[
 {"name":"Certain Sample","budget":1,"bank":(2,2),"seq":(3,)},{"name":"Negative Pair","budget":3,"bank":(3,3),"seq":(2,2)},
 {"name":"Dual Margin","budget":4,"bank":(4,4),"seq":(3,3,1)},{"name":"Paired Evidence","budget":5,"bank":(5,5),"seq":(2,2,3,3,3)},
 {"name":"Safe Ledgers","budget":6,"bank":(6,6),"seq":(3,3,3,2)},{"name":"Vault Evidence","budget":8,"bank":(8,8),"seq":(2,2,2,2,2)}]
def scored(seq):return sum({1:1,2:-2,3:3}[a] for a in seq)
for x in LEVELS:
 score=scored(x["seq"]);assert score and abs(score)>3*(x["budget"]-len(x["seq"]));x["choice"]=0 if score>0 else 1;x["plan"]=x["seq"]+(4+x["choice"],)
def advance(s,a,x):
 bank,evidence,score,used,committed=s;bank=list(bank);evidence=list(evidence)
 if a in (1,2,3):
  if used>=x["budget"]:return None
  if a==1:
   if not bank[0]:return None
   bank[0]-=1;evidence[0]+=1
  elif a==2:
   if not bank[1]:return None
   bank[1]-=1;evidence[1]+=1
  else:
   if not min(bank):return None
   bank[0]-=1;bank[1]-=1;evidence[0]+=1;evidence[1]+=1
  score+={1:1,2:-2,3:3}[a];used+=1
 elif a in (4,5):
  choice=a-4;remaining=x["budget"]-used
  if not score or abs(score)<=3*remaining or choice!=(0 if score>0 else 1):return None
  committed=(choice,tuple(evidence))
 return tuple(bank),tuple(evidence),score,used,committed
def target(x):
 s=(x["bank"],(0,0),0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT
  for i,c in enumerate((SAMPLE1,SAMPLE2,SAMPLE3)):f[8:29,8+i*17:22+i*17]=c
  f[35:39,8:8+g.evidence[0]*5]=A_ECHO;f[42:46,8:8+g.evidence[1]*5]=B_ECHO;f[49:53,8:8+min(abs(g.score),9)*5]=SAMPLE1+(g.score<0)
  if g.committed:f[54:59,39:56]=STOP
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q700(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q700",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bank=self.cfg["bank"];self.evidence=(0,0);self.score=self.used=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.bank,self.evidence,self.score,self.used,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bank,self.evidence,self.score,self.used,self.committed=s
  elif a==6:
   if (self.bank,self.evidence,self.score,self.used,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
