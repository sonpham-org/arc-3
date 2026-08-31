"""q554 Tessera Lesson -- infer a contextual tile macro and interrupt its final action."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TILE,SEAM,DEMO,CONTEXT,WINDOW,GOAL,BAD=1,9,14,10,6,12,11,13,15
LEVELS=[
 {"name":"One Example","seq":(1,)},{"name":"Context Fold","seq":(4,2)},
 {"name":"Null Gesture","seq":(1,3,2)},{"name":"Macro Window","seq":(1,2,4,1)},
 {"name":"Interrupted Pattern","seq":(2,1,3,4,2,1)},
 {"name":"Tessera Lesson","seq":(1,4,2,3,1,2,4,2,1)}]
def advance(s,a):
 context,tile,phase,trace,window,policy=s
 if a==1:tile=(tile+1+context)%9;phase=(phase+1)%4;trace=trace+((context,1,tile),)
 elif a==2:tile=(8-tile+phase)%9;phase=(phase+2)%4;trace=trace+((context,2,tile),)
 elif a==3:trace=trace+((context,0,tile),);window=(window+1)%3
 elif a==4:context^=1;window=(window+phase+context)%3
 elif a==5:policy=(context,tile,phase,trace[-4:],window)
 return context,tile,phase,trace,window,policy
for x in LEVELS:
 s=(0,0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MOSAIC
  for i in range(9):x=8+(i%3)*17;y=8+(i//3)*10;f[y:y+8,x:x+13]=TILE if i==g.tile else SEAM
  for i,(_,a,v) in enumerate(g.trace[-5:]):x=8+i*10;f[39:44,x:x+7]=DEMO if a else WINDOW;f[45:47,x:x+2+v%5]=TILE
  f[50:54,8:8+g.phase*11+7]=CONTEXT;f[56:60,8:8+g.window*15+10]=WINDOW
  if g.policy:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q554(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q554",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.context=self.tile=self.phase=self.window=0;self.trace=();self.policy=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.context,self.tile,self.phase,self.trace,self.window,self.policy=advance((self.context,self.tile,self.phase,self.trace,self.window,self.policy),a)
  elif a==6:
   if (self.context,self.tile,self.phase,self.trace,self.window,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
