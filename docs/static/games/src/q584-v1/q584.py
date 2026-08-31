"""q584 Tessera Counter -- shape a mosaic rival before interrupting its repeated macro."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TILE,SEAM,WINDOW,RIVAL,HISTORY,GOAL,BAD=2,10,14,9,6,12,11,13,15
LEVELS=[
 {"name":"First Tactic","seq":(1,)},{"name":"Second Treatment","seq":(2,1)},
 {"name":"Seam Response","seq":(3,1,2)},{"name":"Macro Counter","seq":(1,4,2,3)},
 {"name":"Shape The Fold","seq":(2,3,1,4,2,1)},
 {"name":"Tessera Counter","seq":(3,1,2,4,1,3,2,1,4)}]
def advance(s,a):
 recent,rival,tile,seam,window,exploit=s
 if a in (1,2):recent=(recent+(a,))[-2:];tile=(tile+a+rival)%9;rival=(sum(recent)+tile+seam)%3
 elif a==3:seam=(seam+1+rival)%5;tile=(8-tile+seam)%9
 elif a==4:window=(window+1+seam)%4;rival=(rival+window)%3
 elif a==5:exploit=(recent,rival,tile,seam,window)
 return recent,rival,tile,seam,window,exploit
for x in LEVELS:
 s=((),0,0,0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MOSAIC
  for i in range(9):x=8+(i%3)*17;y=8+(i//3)*10;f[y:y+8,x:x+13]=TILE if i==g.tile else SEAM
  for i,a in enumerate(g.recent):f[39:45,9+i*20:23+i*20]=HISTORY;f[41:43,12+i*20:12+i*20+a*4]=TILE
  f[49:53,8:8+g.rival*16+8]=RIVAL;f[55:59,8:8+g.window*11+7]=WINDOW
  if g.exploit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q584(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q584",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.rival=self.tile=self.seam=self.window=0;self.exploit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.recent,self.rival,self.tile,self.seam,self.window,self.exploit=advance((self.recent,self.rival,self.tile,self.seam,self.window,self.exploit),a)
  elif a==6:
   if (self.recent,self.rival,self.tile,self.seam,self.window,self.exploit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
