"""q701 Pollen Evidence -- stop safely after unequal samples cross a wear inversion."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,SAMPLE1,SAMPLE2,SAMPLE3,SCORE,WEAR,STOP,BAD=5,14,10,12,11,9,13,6,15
LEVELS=[
 {"name":"Certain Sample","budget":1,"wear":9,"seq":(3,)},{"name":"Negative Pair","budget":3,"wear":9,"seq":(2,2)},
 {"name":"Inverted Tail","budget":4,"wear":2,"seq":(3,3,1)},{"name":"Worn Evidence","budget":5,"wear":2,"seq":(2,2,3,3)},
 {"name":"Safe Margin","budget":6,"wear":3,"seq":(3,3,3,2)},{"name":"Pollen Evidence","budget":8,"wear":3,"seq":(2,2,2,3,3)}]
def score_seq(x):
 score=rule=used=0
 for a in x["seq"]:
  v={1:1,2:-2,3:3}[a];score+=-v if rule else v;used+=1
  if used==x["wear"]:rule^=1
 assert score and abs(score)>3*(x["budget"]-used)
 return score
for x in LEVELS:
 score=score_seq(x);x["choice"]=0 if score>0 else 1;x["plan"]=x["seq"]+(4+x["choice"],)
def advance(s,a,x):
 score,used,rule,committed=s
 if a in (1,2,3):
  if used>=x["budget"]:return None
  v={1:1,2:-2,3:3}[a];score+=-v if rule else v;used+=1
  if used==x["wear"]:rule^=1
 elif a in (4,5):
  remaining=x["budget"]-used;choice=a-4
  if not score or abs(score)<=3*remaining or choice!=(0 if score>0 else 1):return None
  committed=choice
 return score,used,rule,committed
def target(x):
 s=(0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MEADOW
  for i,c in enumerate((SAMPLE1,SAMPLE2,SAMPLE3)):f[8:29,8+i*17:22+i*17]=c
  width=min(abs(g.score),12)*4;f[35:40,32-width//2:32+width//2]=SCORE+(g.score<0);f[44:48,8:8+g.used*6]=WEAR;f[52:57,8:28]=SAMPLE1+g.rule
  if g.committed is not None:f[52:59,39:56]=STOP+g.committed
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q701(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q701",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.score=self.used=self.rule=0;self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.score,self.used,self.rule,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.score,self.used,self.rule,self.committed=s
  elif a==6:
   if (self.score,self.used,self.rule,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
