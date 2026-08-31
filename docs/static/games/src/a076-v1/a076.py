"""a076 Scissor Lift -- trade height, footprint, and actuation point."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,YARD,LINK,JOINT,PLATFORM,CARGO,LEDGE,BOUNDARY,ACTUATOR,BAD=4,8,9,14,12,10,11,13,6,15
LEVELS=[
 {"name":"Close Base","seq":(1,)},{"name":"Choose Joint","seq":(2,)},
 {"name":"Raise Cargo","seq":(1,3)},{"name":"Clear Ledge","seq":(2,1,3,4)},
 {"name":"Respect Boundary","seq":(1,2,3,1,4,3,2)},{"name":"Scissor Lift","seq":(2,1,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 height,width,point,lateral,stress,history,snapshot=s
 if a==1:width=max(2,width-1);height=min(7,height+1+point);stress=(stress+point)%6;history=(history+(1,))[-8:]
 elif a==2:point=(point+1)%3;history=(history+(2,))[-8:]
 elif a==3:height=min(8,height+point);width=max(2,width-point);stress=(stress+1)%6;history=(history+(3,))[-8:]
 elif a==4:lateral=(lateral+1+width)%7;history=(history+(4,))[-8:]
 elif a==5:snapshot=(height,width,point,lateral,stress,history)
 return height,width,point,lateral,stress,history,snapshot
for x in LEVELS:
 s=(2,7,0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD;cx=29+g.lateral*2;base=46;top=base-g.height*4;half=g.width*2
  for level in range(3):
   y0=base-level*(base-top)//3;y1=base-(level+1)*(base-top)//3
   for i in range(13):
    x1=cx-half+2*half*i//12;x2=cx+half-2*half*i//12;y=y0+(y1-y0)*i//12;f[y:y+3,x1:x1+3]=LINK;f[y:y+3,x2:x2+3]=LINK
  f[top-3:top+2,cx-half:cx+half+3]=PLATFORM;f[top-11:top-3,cx-5:cx+6]=CARGO
  f[16:39,50:56]=LEDGE;f[9:55,5:8]=BOUNDARY;f[9:55,57:60]=BOUNDARY
  f[50:55,10:10+g.point*9]=ACTUATOR
  for i in range(g.stress):f[55:58,35+i*3:38+i*3]=BAD
  if g.bad:f[1:4,18:46]=BAD
  return f
class A076(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a076",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.height,self.width,self.point,self.lateral,self.stress,self.history,self.snapshot=(2,7,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.height,self.width,self.point,self.lateral,self.stress,self.history,self.snapshot=advance((self.height,self.width,self.point,self.lateral,self.stress,self.history,self.snapshot),a)
  elif a==6:
   if (self.height,self.width,self.point,self.lateral,self.stress,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
