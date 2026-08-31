"""a029 Latent Cursor -- preserve invisible selection while objects cross."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ROOM,OBJECT,HIGHLIGHT,SELECTED,TRACK,TRACE,GOAL,BAD=8,10,14,11,12,6,5,13,15
LEVELS=[{"name":"Visible Highlight","seq":(1,)},{"name":"Hidden Selection","seq":(2,1)},{"name":"Remote Move","seq":(3,1,2)},{"name":"Crossing Objects","seq":(4,2,1,3)},{"name":"Latent Binding","seq":(2,3,1,4,2,1)},{"name":"Latent Cursor","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 positions,highlight,selected,visible,history,remote=s;p=list(positions)
 if a==1:highlight=(highlight+1)%3;visible=True
 elif a==2:selected=highlight;visible=False;history=history+(("select",selected,tuple(p)),)
 elif a==3:p[selected]=(p[selected]+2)%10;history=history+(("move",selected,tuple(p)),)
 elif a==4:p[0],p[2]=p[2],p[0];highlight=(highlight+2)%3;visible=(len(history)%4==0);history=history+(("cross",selected,tuple(p)),)
 elif a==5:remote=(tuple(p),highlight,selected,visible,history[-5:])
 return tuple(p),highlight,selected,visible,history,remote
for x in LEVELS:
 s=((1,5,8),0,0,True,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ROOM
  for lane,p in enumerate(g.positions):y=9+lane*12;f[y:y+8,7:57]=TRACK;x=8+p*5;f[y:y+8,x:x+5]=HIGHLIGHT if g.visible and lane==g.highlight else SELECTED if lane==g.selected else OBJECT
  for i,_ in enumerate(g.history[-4:]):f[47:52,8+i*12:17+i*12]=TRACE
  if g.remote:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A029(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a029",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions=(1,5,8);self.highlight=self.selected=0;self.visible=True;self.history=();self.remote=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.highlight,self.selected,self.visible,self.history,self.remote=advance((self.positions,self.highlight,self.selected,self.visible,self.history,self.remote),a)
  elif a==6:
   if (self.positions,self.highlight,self.selected,self.visible,self.history,self.remote)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
