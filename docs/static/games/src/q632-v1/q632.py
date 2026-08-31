"""q632 Lockwater Sandbox -- reset canal trials while identity evidence survives."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,CANAL,BARGE,WATER,EVIDENCE,RESET,GOAL,BAD=4,8,11,14,10,6,12,13,15
LEVELS=[
 {"name":"First Trial","seq":(1,3)},{"name":"Swapped Barge","seq":(2,3,4)},
 {"name":"Persistent Wake","seq":(1,3,4,2,3)},{"name":"Identity Contrast","seq":(2,1,3,4,1,3)},
 {"name":"Coupled Levels","seq":(1,2,3,4,2,2,3)},
 {"name":"Lockwater Sandbox","seq":(2,1,3,4,1,2,3,4,2,3)}]
def advance(s,a):
 positions,colors,levels,evidence,trials,commit=s;p=list(positions);c=list(colors);w=list(levels)
 if a==1:p[0],p[1]=p[1],p[0];w[0]=(w[0]+1)%5;w[1]=(w[1]-1)%5
 elif a==2:c[1],c[2]=c[2],c[1];p=p[1:]+p[:1];w=w[-1:]+w[:-1]
 elif a==3:evidence=evidence+((tuple(p),tuple(c),tuple(w)),);trials+=1
 elif a==4:p[:]=[0,1,2];c[:]=[0,1,2];w[:]=[1,2,3]
 elif a==5:commit=(tuple(p),tuple(c),tuple(w),evidence[-3:],trials)
 return tuple(p),tuple(c),tuple(w),evidence,trials,commit
for x in LEVELS:
 s=((0,1,2),(0,1,2),(1,2,3),(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;f[8:31,7:29]=CANAL;f[8:31,35:57]=RESET
  for i,(p,c,w) in enumerate(zip(g.positions,g.colors,g.levels)):
   x=9+p*7;f[25-w*3:29,x:x+6]=BARGE if c%2 else WATER
  for i,e in enumerate(g.evidence[-5:]):x=8+i*10;f[36:42,x:x+7]=EVIDENCE;f[43:46,x:x+2+sum(e[2])%5]=WATER
  f[50:54,8:8+min(g.trials,5)*9+5]=EVIDENCE
  if g.commit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q632(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q632",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions=(0,1,2);self.colors=(0,1,2);self.levels=(1,2,3);self.evidence=();self.trials=0;self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.colors,self.levels,self.evidence,self.trials,self.commit=advance((self.positions,self.colors,self.levels,self.evidence,self.trials,self.commit),a)
  elif a==6:
   if (self.positions,self.colors,self.levels,self.evidence,self.trials,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
