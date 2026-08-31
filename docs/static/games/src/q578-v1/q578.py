"""q578 Asterism Counter -- shape a rival through a precessing treatment history."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,STAR,RIVAL,TACTIC0,TACTIC1,TACTIC2,MEMORY,GOAL,BAD=2,7,11,14,10,9,12,6,13,15
LEVELS=[
 {"name":"Single Treatment","seq":(1,)},{"name":"Two-Step Rival","seq":(1,2)},
 {"name":"Precessed Counter","seq":(1,3,2)},{"name":"Persistent History","seq":(2,1,4,2)},
 {"name":"Shaped Orbit","seq":(1,2,3,1,4,2)},{"name":"Asterism Counter","seq":(2,1,3,2,2,4,1,3,2)}]
def advance(s,a):
 history,phase,pos,rival,exploited=s
 if a in (1,2):
  history=(history+(a-1,))[-3:];pos=(pos+a+phase)%8;rival=(sum((i+1)*v for i,v in enumerate(history))+phase)%3
 elif a==3:phase=(phase+1)%3;rival=(rival+1)%3
 elif a==4:pos=0
 elif a==5:exploited=(rival,pos,phase,history)
 return history,phase,pos,rival,exploited
for x in LEVELS:
 s=((),0,0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["goal"]=s[3];x["plan"]=x["seq"]+(5,)
def target(x):
 s=((),0,0,0,None)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i in range(8):
   x=8+i*6;f[10+(i%2)*5:14+(i%2)*5,x:x+4]=STAR if i!=g.pos else GOAL
  cols=(TACTIC0,TACTIC1,TACTIC2)
  for i,c in enumerate(cols):f[28:42,8+i*18:22+i*18]=c if i==g.rival else RIVAL
  for i,v in enumerate(g.history):f[47:52,8+i*11:16+i*11]=cols[v]
  f[54:58,40:40+g.phase*6+4]=MEMORY
  if g.exploited:f[56:60,8:28]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q578(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q578",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.history=();self.phase=self.pos=self.rival=0;self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.history,self.phase,self.pos,self.rival,self.exploited=advance((self.history,self.phase,self.pos,self.rival,self.exploited),a)
  elif a==6:
   if (self.history,self.phase,self.pos,self.rival,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
